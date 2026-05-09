from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Scalping Bot")

STATE_FILE = Path(os.getenv("CANDLES_STATE_FILE", "candles_state.json"))
MAX_STORED_CANDLES = int(os.getenv("MAX_STORED_CANDLES", os.getenv("BOT_BARS", "300")))
SEND_HOLD_SIGNALS = os.getenv("SEND_HOLD_SIGNALS", "false").lower() == "true"


class Candle(BaseModel):
    time: Optional[str] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0


class SignalRequest(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    candles: List[Candle]


class TradingViewWebhook(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    time: Optional[str] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0


@app.get("/")
def root():
    return {"status": "online"}


@app.get("/health")
def health():
    return {"status": "ok"}


def telegram_enabled() -> bool:
    return (
        os.getenv("BOT_TELEGRAM", "false").lower() == "true"
        and bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        and bool(os.getenv("TELEGRAM_CHAT_ID"))
    )


def send_telegram(text: str) -> None:
    if not telegram_enabled():
        return

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    parse_mode = os.getenv("TELEGRAM_PARSE_MODE", "HTML")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()


def format_signal(signal: dict) -> str:
    action = signal.get("action", "HOLD")
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(action, "⚪")
    esc = html.escape

    return "\n".join(
        [
            f"{emoji} <b>{esc(action)}</b> | {esc(signal['symbol'])} {esc(signal['timeframe'])}",
            f"Entrada: <b>{signal['entry']}</b>",
            f"Stop Loss: <b>{signal['stop_loss']}</b>",
            f"Take Profit: <b>{signal['take_profit']}</b>",
            f"Confiança: <b>{signal['confidence']}%</b>",
            f"Motivo: {esc(signal['reason'])}",
            f"Horário: {esc(signal['timestamp_utc'])}",
        ]
    )


def maybe_send_signal(signal: dict) -> None:
    if signal.get("action") == "HOLD" and not SEND_HOLD_SIGNALS:
        return
    send_telegram(format_signal(signal))


def generate_signal(symbol: str, timeframe: str, candles: List[Candle]) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    if len(candles) < 2:
        return {
            "timestamp_utc": now,
            "symbol": symbol,
            "timeframe": timeframe,
            "action": "HOLD",
            "reason": "Aguardando pelo menos 2 candles fechados",
            "entry": candles[-1].close if candles else None,
            "stop_loss": None,
            "take_profit": None,
            "confidence": 0,
            "candles_count": len(candles),
        }

    last = candles[-1]
    prev = candles[-2]
    entry = float(last.close)

    if last.close > prev.close:
        action = "BUY"
        stop_loss = round(entry * 0.998, 5)
        take_profit = round(entry * 1.002, 5)
        reason = "Último candle fechou acima do candle anterior"
    elif last.close < prev.close:
        action = "SELL"
        stop_loss = round(entry * 1.002, 5)
        take_profit = round(entry * 0.998, 5)
        reason = "Último candle fechou abaixo do candle anterior"
    else:
        action = "HOLD"
        stop_loss = None
        take_profit = None
        reason = "Último candle fechou igual ao candle anterior"

    return {
        "timestamp_utc": last.time or now,
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "reason": reason,
        "entry": round(entry, 5),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "confidence": 72 if action != "HOLD" else 0,
        "candles_count": len(candles),
    }


def _state_key(symbol: str, timeframe: str) -> str:
    return f"{symbol.upper()}::{timeframe.upper()}"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def append_candle(symbol: str, timeframe: str, candle: Candle) -> List[Candle]:
    state = load_state()
    key = _state_key(symbol, timeframe)
    raw_candles = state.get(key, [])

    candle_dict = candle.model_dump()

    # Evita duplicar candle quando o TradingView reenvia a mesma barra.
    if raw_candles and candle.time and raw_candles[-1].get("time") == candle.time:
        raw_candles[-1] = candle_dict
    else:
        raw_candles.append(candle_dict)

    raw_candles = raw_candles[-MAX_STORED_CANDLES:]
    state[key] = raw_candles
    save_state(state)
    return [Candle(**item) for item in raw_candles]


@app.post("/signal")
def signal(payload: SignalRequest):
    signal_result = generate_signal(payload.symbol, payload.timeframe, payload.candles)
    try:
        maybe_send_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc
    return signal_result


@app.post("/webhook/tradingview")
def tradingview_webhook(payload: TradingViewWebhook):
    candle = Candle(
        time=payload.time,
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
    )
    candles = append_candle(payload.symbol, payload.timeframe, candle)
    signal_result = generate_signal(payload.symbol, payload.timeframe, candles)

    try:
        maybe_send_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc

    return signal_result


@app.post("/telegram/test")
def telegram_test():
    if not telegram_enabled():
        raise HTTPException(
            status_code=400,
            detail="Telegram desativado. Configure BOT_TELEGRAM=true, TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.",
        )
    send_telegram("✅ Bot conectado ao Telegram e pronto para receber candles.")
    return {"status": "sent"}


@app.get("/candles/status")
def candles_status():
    state = load_state()
    return {
        "state_file": str(STATE_FILE),
        "markets": {key: len(value) for key, value in state.items()},
    }
