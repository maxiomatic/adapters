#!/bin/bash
set -euo pipefail

# Oracle: replay the verified human action list through the same REST API the agent uses.
python3 /solution/replay_oracle.py /solution/oracle_actions.json
