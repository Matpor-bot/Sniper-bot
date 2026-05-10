"""Compatibilidade para plataformas que executam `python main.py`."""
from app import app  # noqa: F401
from start import get_port

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=get_port(), proxy_headers=True)
