"""Entrypoint seguro para Railway.
Lê PORT pelo Python, evitando o erro: '$PORT' is not a valid integer.
"""
import os
import uvicorn


def get_port() -> int:
    raw = os.environ.get("PORT", "8000")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 8000


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=get_port(), proxy_headers=True)
