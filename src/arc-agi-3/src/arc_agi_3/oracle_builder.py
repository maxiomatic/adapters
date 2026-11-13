"""Rebuild `oracle_solutions/*.json` from ARC Prize's public human replay dataset.

Dataset: "ARC-AGI-3 Human Baseline [Public]"
(https://drive.google.com/drive/folders/1FB7yae6VISRe2jDKPNZLJS0mAqIw9JZy, linked from
https://arcprize.org/blog/arc-agi-3-human-dataset), file
`arc_agi_3_public_demo_human_testing.zip`, SHA-256
99a32ffc3b9e55bc3077b979d00906f256c26354b5fada0b052690b2f5cd634a.

For each game and level, the oracle takes the human session that completed that level in
the fewest actions and uses that session's actions for the level (everything after the
previous level was completed, up to and including the completing action). Levels are joined
in order. This is the ARC-AGI-3 Technical Report's "best first-run playthrough" (sec. 5.3.2).

Usage (from src/arc-agi-3):
    uv run python -m arc_agi_3.oracle_builder <extracted>/public_games-dataset src/arc_agi_3/oracle_solutions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ACTION_IDS = {"RESET": 0, **{f"ACTION{i}": i for i in range(1, 8)}}
ACTION_NAMES = {v: k for k, v in ACTION_IDS.items()}


def level_segments(path: Path) -> tuple[str | None, dict[int, list[dict]]]:
    """Return (game version, {level_index: actions}) for the first play in a recording."""
    version, segments, current, levels_prev, started = None, {}, [], 0, False
    with path.open("rb") as f:
        for line in f:
            data = json.loads(line)["data"]
            if "action_input" not in data:
                continue
            version = version or data["game_id"]
            action_input = data["action_input"]
            raw_id = action_input["id"]
            action_id = raw_id if isinstance(raw_id, int) else ACTION_IDS[raw_id]
            if action_id == 0 and (data.get("full_reset") or not started):
                if started and segments:
                    break  # a second play begins; keep the first
                started, current, levels_prev = True, [], 0
                continue
            started = True
            action = {"action": ACTION_NAMES[action_id]}
            payload = action_input.get("data") or {}
            if "x" in payload and "y" in payload:
                action["x"], action["y"] = int(payload["x"]), int(payload["y"])
            current.append(action)
            levels = int(data["levels_completed"])
            if levels > levels_prev:
                segments[levels_prev] = current
                current, levels_prev = [], levels
    return version, segments


def build(replay_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for game_dir in sorted(p for p in replay_dir.iterdir() if p.is_dir()):
        best: dict[int, tuple[str, list[dict]]] = {}
        version = None
        for rec in sorted(game_dir.glob("*.recording.jsonl")):
            v, segments = level_segments(rec)
            version = version or v
            for level, actions in segments.items():
                if level not in best or len(actions) < len(best[level][1]):
                    best[level] = (rec.name, actions)
        actions, levels = [], []
        for level in sorted(best):
            source, segment = best[level]
            actions += segment
            levels.append({"level": level + 1, "source_file": f"{game_dir.name}/{source}",
                           "n_actions": len(segment)})
        (out_dir / f"{game_dir.name}.json").write_text(
            json.dumps({"game_id": version, "actions": actions, "levels": levels})
        )
        print(f"{game_dir.name}: {len(levels)} levels, {len(actions)} actions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("replay_dir", type=Path, help="extracted public_games-dataset directory")
    parser.add_argument("out_dir", type=Path, help="output directory for <game>.json files")
    args = parser.parse_args()
    build(args.replay_dir, args.out_dir)


if __name__ == "__main__":
    main()
