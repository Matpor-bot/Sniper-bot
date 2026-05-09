#!/bin/sh
set -e

# Use the PORT provided by the hosting platform, or 8000 locally.
PORT="${PORT:-8000}"

exec uvicorn app:app --host 0.0.0.0 --port "$PORT"
