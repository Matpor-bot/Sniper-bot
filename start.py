"""Production entrypoint for Railway/Render/etc.
Reads PORT from the environment in Python instead of relying on shell expansion.
"""
import os
import uvicorn


def get_port() -> int:
    raw = os.environ.get("PORT", "8000")
    try:
        return int(raw)
    except (TypeError, ValueError):
        # Safe local fallback. In production, PORT should be set by the platform.
        return 8000


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=get_port())
