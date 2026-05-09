from __future__ import annotations

import importlib.util
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import settings
from .schemas import Candle, SignalPayload, SignalResponse
from .storage import SignalStore
from .strategy import SignalEngine, normalize_df
from .telegram import TelegramNotifier

try:
    from fastapi import FastAPI, HTTPException
except Exception:  # pragma: no cover
    FastAPI = None
    HTTPException = Exception  # type: ignore

MT5_AVAILABLE = importlib.util.find_spec("MetaTrader5") is not None
if MT5_AVAILABLE:
    import MetaTrader5 as mt5  # type: ignore
else:
    mt5 = None

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="[%(levelname)s] %(message)s")
logger = logging.getLogger("scalping-bot")

app = FastAPI(title="Scalping Signal Bot", version="2.0.0") if FastAPI else None
engine = SignalEngine(settings)
storage = SignalStore(settings)
notifier = TelegramNotifier(settings)


def _candles_to_df(candles: list[dict]) -> pd.DataFrame:
    return normalize_df(pd.DataFrame(candles))


def _attach_signal_id(signal: dict) -> dict:
    signal = dict(signal)
    signal["signal_id"] = storage.signal_id(signal)
    return signal


def _maybe_send(signal: dict) -> None:
    if signal["action"] == "HOLD":
        return
    try:
        notifier.send_signal(signal)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Telegram send failed: %s", exc)


if app is not None:

    @app.on_event("startup")
    def startup_event() -> None:
        logger.info("Starting scalping bot for %s %s", settings.symbol, settings.timeframe)
        if notifier.enabled() and settings.telegram_alert_on_startup:
            try:
                notifier.send_startup("Scalping Signal Bot", "online")
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Startup Telegram alert failed: %s", exc)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "scalping-signal-bot",
            "symbol": settings.symbol,
            "timeframe": settings.timeframe,
            "utc": datetime.now(timezone.utc).isoformat(),
            "telegram_enabled": notifier.enabled(),
            "storage_ready": True,
        }

    @app.get("/latest")
    def latest() -> dict:
        latest_signal = storage.latest()
        if not latest_signal:
            raise HTTPException(status_code=404, detail="No signal stored yet")
        return latest_signal

    @app.post("/signal", response_model=SignalResponse)
    def signal_endpoint(payload: SignalPayload) -> dict:
        try:
            df = _candles_to_df([c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in payload.candles])
            signal = engine.generate_signal(df, symbol=payload.symbol, timeframe=payload.timeframe)
            signal = _attach_signal_id(signal)
            persisted = storage.persist(signal)
            _maybe_send(persisted)
            return persisted
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/signal/csv", response_model=SignalResponse)
    def signal_csv(path: str) -> dict:
        try:
            df = normalize_df(pd.read_csv(path))
            signal = engine.generate_signal(df)
            signal = _attach_signal_id(signal)
            persisted = storage.persist(signal)
            _maybe_send(persisted)
            return persisted
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/signal/text")
    def signal_text(payload: SignalPayload) -> dict:
        return signal_endpoint(payload)

    @app.post("/run-once")
    def run_once(mode: str = "csv", path: Optional[str] = None) -> dict:
        try:
            if mode == "csv":
                if not path:
                    raise ValueError("path is required for csv mode")
                df = normalize_df(pd.read_csv(path))
            elif mode == "mt5":
                df = _load_mt5()
            else:
                raise ValueError("mode must be csv or mt5")
            signal = engine.generate_signal(df)
            signal = _attach_signal_id(signal)
            persisted = storage.persist(signal)
            _maybe_send(persisted)
            return persisted
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))


def _load_mt5() -> pd.DataFrame:
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 not installed")
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    if settings.mt5_login and settings.mt5_password and settings.mt5_server:
        if not mt5.login(settings.mt5_login, password=settings.mt5_password, server=settings.mt5_server):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    mapping = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}
    tf = mapping.get(settings.timeframe.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {settings.timeframe}")
    rates = mt5.copy_rates_from_pos(settings.symbol, tf, 0, settings.bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates received for {settings.symbol}")
    df = pd.DataFrame(rates)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return normalize_df(df)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("scalping_bot.app:app", host="0.0.0.0", port=port, reload=False)
