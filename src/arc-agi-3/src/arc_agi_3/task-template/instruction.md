You are playing a game. Your goal is to win. Include any context you want to carry forward in your reply, along with the action you want to take. The final action mentioned in your reply will be executed next turn.

## Game interface

The game is served by the ARC-AGI-3 REST API at `http://game:8001`. Send JSON bodies with the headers `Content-Type: application/json` and `X-API-Key: harbor` (any value works).

- Game ID: `{game_id}`
- Open a scorecard: `POST /api/scorecard/open` with body `{}`. The response contains `card_id`.
- Start the game: `POST /api/cmd/RESET` with body `{"game_id": "{game_id}", "card_id": "<card_id>"}`. The response contains `guid`.
- Take an action: `POST /api/cmd/ACTION1` … `/api/cmd/ACTION5` or `/api/cmd/ACTION7` with body `{"game_id": "{game_id}", "guid": "<guid>"}`.
- `ACTION6` also takes coordinates: body `{"game_id": "{game_id}", "guid": "<guid>", "x": <0-63>, "y": <0-63>}`.
- Reset the current level: `POST /api/cmd/RESET` with body `{"game_id": "{game_id}", "card_id": "<card_id>", "guid": "<guid>"}`.

Every response contains `frame` (a list of 64×64 grids of integers 0–15), `state` (`NOT_FINISHED`, `WIN` or `GAME_OVER`), `levels_completed`, `win_levels` and `available_actions` (the action numbers you may use now). After `GAME_OVER`, only `RESET` is accepted. Every action, including a level reset, counts as an action.
