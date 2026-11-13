FROM python:3.12-slim

# The agent plays through ARC Prize's REST API on the `game` service (http://game:8001).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /logs
