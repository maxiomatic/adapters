"""Replay the oracle action list through ARC's REST API (the same API the agent uses).

Oracle provenance: per level, the fewest-action segment from ARC Prize's public human
replay dataset ("best first-run playthrough", ARC-AGI-3 Technical Report sec. 5.3.2).
See the adapter README for the dataset link and checksum.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

SERVER = os.environ.get("ARC_SERVER", "http://game:8001")
HEADERS = {"Content-Type": "application/json", "X-API-Key": "harbor-oracle"}


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{SERVER}{path}", data=json.dumps(body).encode(), headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def wait_for_server() -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{SERVER}/api/healthcheck", timeout=5):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    raise SystemExit(f"game server at {SERVER} did not become healthy")


def main(path: str) -> None:
    oracle = json.load(open(path))
    game_id = oracle["game_id"]
    wait_for_server()
    card_id = post("/api/scorecard/open", {})["card_id"]
    frame = post("/api/cmd/RESET", {"game_id": game_id, "card_id": card_id})
    guid = frame["guid"]
    for step, act in enumerate(oracle["actions"], start=1):
        body = {"game_id": game_id, "guid": guid}
        if act["action"] == "RESET":
            body["card_id"] = card_id
        if "x" in act:
            body["x"], body["y"] = act["x"], act["y"]
        frame = post(f"/api/cmd/{act['action']}", body)
    print(
        f"oracle replayed {len(oracle['actions'])} actions: state={frame['state']} "
        f"levels_completed={frame['levels_completed']}/{frame['win_levels']}"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/solution/oracle_actions.json")
