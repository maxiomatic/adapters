#!/bin/bash
set -uo pipefail

# Reads the official ARC-AGI-3 RHAE score from the game server (token-protected route)
# and writes reward = score / 100 to /logs/verifier/reward.txt.
mkdir -p /logs/verifier

python3 - <<'EOF'
import json
import os
import urllib.request
from pathlib import Path

reward_file = Path("/logs/verifier/reward.txt")
detail_file = Path("/logs/verifier/arc_agi_3_result.json")
url = f"http://game:8001/harbor/result?token={os.environ.get('RESULT_TOKEN', '')}"
try:
    with urllib.request.urlopen(url, timeout=60) as r:
        result = json.loads(r.read())
    reward = float(result["reward"])
    detail_file.write_text(json.dumps(result, indent=2))
    print(f"RHAE score: {result.get('rhae_score')}  reward: {reward}")
except Exception as exc:
    reward = 0.0
    print(f"Could not read result from game server: {exc}")
reward_file.write_text(str(reward))
EOF
exit 0
