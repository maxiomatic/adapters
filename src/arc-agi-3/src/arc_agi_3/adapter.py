"""
Adapter that generates one Harbor task per ARC-AGI-3 public game.

Each task runs ARC Prize's own game server (arc_agi toolkit, competition mode) for a single
game in a separate `game` container; the agent plays it through ARC's REST API. The oracle
replays a verified human action list (see oracle_builder.py) through the same API, and the
verifier reads the official RHAE score from the game server.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
ORACLE_DIR = PACKAGE_DIR / "oracle_solutions"
DEFAULT_GAMES_CACHE = Path.home() / ".cache" / "arc-agi-3" / "environment_files"

# Template files that contain placeholders; all other files are copied verbatim.
RENDERED_FILES = ("task.toml", "instruction.md", "environment/docker-compose.yaml")


class ARCAGI3Adapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        games_dir: Path | None = None,
        **kwargs,
    ):
        """
        Args:
            output_dir: The directory to write the generated tasks to.
            limit: The maximum number of tasks to generate.
            overwrite: Whether to overwrite existing tasks.
            task_ids: The task IDs (4-character game IDs, e.g. "ls20") to generate.
            games_dir: Directory of downloaded ARC-AGI-3 game files
                (`<game>/<version>/{<game>.py, metadata.json}`). If omitted, the pinned game
                versions are downloaded with the arc_agi toolkit (requires ARC_API_KEY).
        """
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.games_dir = Path(games_dir) if games_dir else None

    # ── inputs ───────────────────────────────────────────────────────────

    @staticmethod
    def load_oracles() -> dict[str, dict]:
        """Oracle action lists keyed by task ID; they also pin each game's version."""
        return {p.stem: json.loads(p.read_text()) for p in sorted(ORACLE_DIR.glob("*.json"))}

    def _download_games(self, game_ids: list[str]) -> Path:
        """Download the pinned game versions with ARC Prize's toolkit (needs ARC_API_KEY)."""
        if not os.environ.get("ARC_API_KEY"):
            raise SystemExit(
                "No --games-dir given and ARC_API_KEY is not set. A registered ARC API key "
                "(https://arcprize.org) is required to download all 25 public games."
            )
        import arc_agi

        DEFAULT_GAMES_CACHE.mkdir(parents=True, exist_ok=True)
        arcade = arc_agi.Arcade(environments_dir=str(DEFAULT_GAMES_CACHE))
        for game_id in game_ids:
            if arcade.make(game_id) is None:
                raise SystemExit(f"Could not download {game_id}")
        return DEFAULT_GAMES_CACHE

    @staticmethod
    def _game_folder(games_dir: Path, game_id: str) -> Path:
        short, version = game_id.split("-", 1)
        folder = games_dir / short / version
        meta = folder / "metadata.json"
        if not meta.is_file():
            raise SystemExit(f"Game files for {game_id} not found at {folder}")
        found = json.loads(meta.read_text()).get("game_id")
        if found != game_id:
            raise SystemExit(f"{meta}: game_id {found!r} does not match pinned {game_id!r}")
        return folder

    # ── generation ───────────────────────────────────────────────────────

    def run(self) -> None:
        oracles = self.load_oracles()
        task_ids = sorted(oracles)
        if self.task_ids:
            unknown = sorted(set(self.task_ids) - set(oracles))
            if unknown:
                raise SystemExit(f"Unknown task IDs: {unknown}. Available: {task_ids}")
            task_ids = [t for t in task_ids if t in set(self.task_ids)]
        if self.limit is not None:
            task_ids = task_ids[: self.limit]

        games_dir = self.games_dir or self._download_games([oracles[t]["game_id"] for t in task_ids])

        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for task_id in task_ids:
            task_dir = self.output_dir / task_id
            if task_dir.exists():
                if not self.overwrite:
                    print(f"skip {task_id}: exists (use --overwrite)")
                    continue
                shutil.rmtree(task_dir)
            self._write_task(task_dir, task_id, oracles[task_id], games_dir)
            written += 1
            print(f"wrote {task_dir}")
        print(f"Done: {written} task(s) written to {self.output_dir}")

    def _write_task(self, task_dir: Path, task_id: str, oracle: dict, games_dir: Path) -> None:
        game_id = oracle["game_id"]
        source = self._game_folder(games_dir, game_id)
        metadata = json.loads((source / "metadata.json").read_text())

        shutil.copytree(TEMPLATE_DIR, task_dir)

        values = {
            "{task_id}": task_id,
            "{game_id}": game_id,
            "{result_token}": secrets.token_hex(16),
            "{levels}": str(len(metadata.get("baseline_actions", []))),
            "{tags_json}": json.dumps(["arc-agi-3", "interactive", *metadata.get("tags", [])]),
        }
        for rel in RENDERED_FILES:
            path = task_dir / rel
            text = path.read_text()
            for key, value in values.items():
                text = text.replace(key, value)
            path.write_text(text)

        # Exactly this one game goes into the game container.
        short, version = game_id.split("-", 1)
        shutil.copytree(source, task_dir / "environment" / "game" / "environment_files" / short / version)

        (task_dir / "solution" / "oracle_actions.json").write_text(json.dumps(oracle))
        for script in ("solution/solve.sh", "tests/test.sh"):
            (task_dir / script).chmod(0o755)
