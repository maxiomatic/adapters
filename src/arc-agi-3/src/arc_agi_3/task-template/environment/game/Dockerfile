FROM python:3.12-slim

# ARC Prize's ARC-AGI-3 toolkit and game engine (pinned to the versions the oracle was verified with).
RUN pip install --no-cache-dir "arc-agi==0.9.10" "arcengine==0.9.3"

WORKDIR /opt/arc
# Exactly one game (source + metadata.json), as downloaded from ARC Prize.
COPY environment_files /opt/arc/environment_files
COPY serve.py /opt/arc/serve.py

EXPOSE 8001
CMD ["python", "/opt/arc/serve.py"]
