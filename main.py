"""Compatibility entrypoint for platforms that auto-run `python main.py`."""
from app import app
from start import get_port

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=get_port())
