"""Launch ARC Prize's own ARC-AGI-3 game server for one game.

This starts the official toolkit server (`arc_agi.Arcade.listen_and_serve`) in
competition mode, the same way the ARC Prize 2026 Kaggle competition runs
submissions (https://docs.arcprize.org/toolkit/listen_and_serve). The agent
plays through ARC's documented REST API (https://docs.arcprize.org/rest_overview).

Two additions are registered through the toolkit's own `extra_api_routes` hook;
no toolkit code is modified:

1. Per-level action budget of ceil(human_baseline * 5), the official ARC-AGI-3
   evaluation rule (ARC-AGI-3 Technical Report sec. 4.3; arc-agi-3-benchmarking
   `MAX_ACTIONS_BASELINE_MULTIPLIER: 5`). Actions are counted exactly as the
   official scorecard counts them. Once the current level's budget is used,
   further game commands are refused.
2. `GET /harbor/result`, a token-protected route the Harbor verifier uses to read
   the official RHAE score. Competition mode hides the scorecard from the agent.
"""

from __future__ import annotations

import logging
import math
import os
import threading

import arc_agi
from arc_agi import OperationMode
from arc_agi.scorecard import EnvironmentScorecard
from flask import Flask, jsonify, request

GAME_ID = os.environ["ARC_GAME_ID"]
RESULT_TOKEN = os.environ["RESULT_TOKEN"]
BUDGET_MULTIPLIER = float(os.environ.get("ARC_BUDGET_MULTIPLIER", "5"))
ENVIRONMENTS_DIR = os.environ.get("ARC_ENVIRONMENTS_DIR", "/opt/arc/environment_files")
PORT = int(os.environ.get("ARC_PORT", "8001"))

logging.basicConfig(level=logging.WARNING)

arcade = arc_agi.Arcade(
    operation_mode=OperationMode.OFFLINE,
    environments_dir=ENVIRONMENTS_DIR,
)
_envs = arcade.get_environments()
if len(_envs) != 1 or _envs[0].game_id != GAME_ID:
    raise SystemExit(
        f"expected exactly game {GAME_ID} in {ENVIRONMENTS_DIR}, found {[e.game_id for e in _envs]}"
    )
BUDGETS = [math.ceil(b * BUDGET_MULTIPLIER) for b in (_envs[0].baseline_actions or [])]

_lock = threading.Lock()
_closed_result: dict | None = None  # filled if the agent closes the scorecard itself


def _open_scorecard():
    scorecards = arcade.scorecard_manager.scorecards
    return next(iter(scorecards.values()), None) if scorecards else None


def _level_actions(card) -> tuple[int, int] | None:
    """(current level index, actions spent on it) for the current play, as the scorecard counts."""
    if card is None or not card.started:
        return None
    idx = card.idx
    level = card.levels_completed[idx]
    checkpoints = card.actions_by_level[idx]
    spent_before = checkpoints[-1][1] if checkpoints else 0
    return level, card.actions[idx] - spent_before


def _score_payload(env_scorecard: EnvironmentScorecard) -> dict:
    data = env_scorecard.model_dump(exclude_none=True)
    data.pop("api_key", None)
    env = next((e for e in data.get("environments", []) if e.get("id") == GAME_ID), None)
    score = float(env["score"]) if env else 0.0
    return {
        "game_id": GAME_ID,
        "reward": max(0.0, min(1.0, score / 100.0)),
        "rhae_score": score,
        "level_action_budgets": BUDGETS,
        "scorecard": data,
    }


def _on_scorecard_close(env_scorecard: EnvironmentScorecard) -> None:
    global _closed_result
    with _lock:
        _closed_result = _score_payload(env_scorecard)


def harbor_routes(arc: arc_agi.Arcade, app: Flask):
    @app.before_request
    def enforce_level_budget():
        if not request.path.startswith("/api/cmd/") or not BUDGETS:
            return None
        sc = _open_scorecard()
        card = sc.cards.get(GAME_ID) if sc else None
        state = _level_actions(card)
        if state is None:
            return None
        level, spent = state
        if level < len(BUDGETS) and spent >= BUDGETS[level]:
            return jsonify(
                {
                    "error": "ACTION_BUDGET_EXHAUSTED",
                    "message": (
                        f"action budget for level {level + 1} is used up "
                        f"({spent}/{BUDGETS[level]}); the run is over"
                    ),
                }
            ), 429
        return None

    @app.route("/harbor/result", methods=["GET"])
    def harbor_result():
        token = request.args.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if token != RESULT_TOKEN:
            return jsonify({"error": "unauthorized"}), 401
        with _lock:
            if _closed_result is not None:
                return jsonify(_closed_result), 200
        sc = _open_scorecard()
        if sc is None:
            return jsonify({"game_id": GAME_ID, "reward": 0.0, "rhae_score": 0.0,
                            "level_action_budgets": BUDGETS, "note": "no scorecard was opened"}), 200
        env_scorecard = EnvironmentScorecard.from_scorecard(sc, arc.available_environments)
        return jsonify(_score_payload(env_scorecard)), 200


if __name__ == "__main__":
    print(f"ARC-AGI-3 server for {GAME_ID} on :{PORT} (level budgets {BUDGETS})", flush=True)
    arcade.listen_and_serve(
        host="0.0.0.0",
        port=PORT,
        competition_mode=True,
        extra_api_routes=harbor_routes,
        on_scorecard_close=_on_scorecard_close,
    )
