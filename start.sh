#!/bin/sh
set -e

# Do not pass --port "$PORT" to uvicorn here; Python reads and validates PORT.
exec python start.py
