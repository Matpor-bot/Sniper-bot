from __future__ import annotations

import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ValidationError

app = FastAPI(title="Scalping Bot")

STATE_FILE = Path(os.getenv("CANDLES_STATE_FILE", "candles_state.json"))
MAX_STORED_CANDLES = int(os.getenv("MAX_STORED_CANDLES", os.getenv("BOT_BARS", "300")))
SEND_HOLD_SIGNALS = os.getenv("SEND_HOLD_SIGNALS", "false").lower() == "true"
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "America/Sao_Paulo")
TIME_FORMAT = os.getenv("BOT_TIME_FORMAT", "%d/%m/%Y %H:%M:%S")
WIN_LOSS_ALERTS = os.getenv("WIN_LOSS_ALERTS", "true").lower() == "true"
SAME_CANDLE_POLICY = os.getenv("SAME_CANDLE_POLICY", "conservative").lower()
MAX_OPEN_SIGNALS = int(os.getenv("MAX_OPEN_SIGNALS", "50"))


class Candle(BaseModel):
    time: Optional[Union[str, int, float]] = None
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
    time: Optional[Union[str, int, float]] = None
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


def get_bot_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(BOT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def parse_timestamp(value: Optional[Union[str, int, float]]) -> datetime:
    """Converte timestamp do TradingView para datetime UTC.

    O TradingView costuma enviar `time` em milissegundos Unix, como
    1778376960000. Também aceitamos segundos Unix e datas ISO.
    """
    if value is None or value == "":
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        raw = str(value).strip()
        try:
            number = float(raw)
        except ValueError:
            try:
                # Suporta ISO com Z no fim.
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)

    # TradingView normalmente manda milissegundos. Segundos Unix são ~10 dígitos;
    # milissegundos são ~13 dígitos.
    if number > 10_000_000_000:
        number = number / 1000.0
    return datetime.fromtimestamp(number, tz=timezone.utc)


def timestamp_fields(value: Optional[Union[str, int, float]]) -> dict:
    dt_utc = parse_timestamp(value)
    dt_local = dt_utc.astimezone(get_bot_timezone())
    return {
        "timestamp_raw": str(value) if value is not None else None,
        "timestamp_utc": dt_utc.isoformat(),
        "timestamp_local": dt_local.strftime(TIME_FORMAT),
        "timezone": BOT_TIMEZONE if get_bot_timezone().key != "UTC" else "UTC",
        "timestamp_display": f"{dt_local.strftime(TIME_FORMAT)} ({BOT_TIMEZONE if get_bot_timezone().key != 'UTC' else 'UTC'})",
    }


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
            f"ID: <code>{esc(signal.get('signal_id', '-'))}</code>",
            f"Entrada: <b>{signal['entry']}</b>",
            f"Stop Loss: <b>{signal['stop_loss']}</b>",
            f"Take Profit: <b>{signal['take_profit']}</b>",
            f"Confiança: <b>{signal['confidence']}%</b>",
            f"Motivo: {esc(signal['reason'])}",
            f"Horário: {esc(signal.get('timestamp_display') or signal.get('timestamp_utc') or '-')}",
        ]
    )


def format_result(result: dict) -> str:
    esc = html.escape
    status = result.get("result", "UNKNOWN")
    emoji = "✅" if status == "WIN" else "❌" if status == "LOSS" else "⚠️"
    signal = result.get("signal", {})

    return "\n".join(
        [
            f"{emoji} <b>{esc(status)}</b> | {esc(signal.get('symbol', '-'))} {esc(signal.get('timeframe', '-'))}",
            f"ID: <code>{esc(signal.get('signal_id', '-'))}</code>",
            f"Operação: <b>{esc(signal.get('action', '-'))}</b>",
            f"Entrada: <b>{signal.get('entry', '-')}</b>",
            f"Stop Loss: <b>{signal.get('stop_loss', '-')}</b>",
            f"Take Profit: <b>{signal.get('take_profit', '-')}</b>",
            f"Preço que confirmou: <b>{result.get('hit_price', '-')}</b>",
            f"Candle: O {result.get('candle_open', '-')} / H {result.get('candle_high', '-')} / L {result.get('candle_low', '-')} / C {result.get('candle_close', '-')}",
            f"Horário: {esc(result.get('timestamp_display', '-'))}",
            f"Motivo: {esc(result.get('reason', '-'))}",
        ]
    )


def maybe_send_signal(signal: dict) -> None:
    if signal.get("action") == "HOLD" and not SEND_HOLD_SIGNALS:
        return
    send_telegram(format_signal(signal))


def make_signal_id(signal: dict) -> str:
    stable = {
        "timestamp_utc": signal.get("timestamp_utc"),
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "action": signal.get("action"),
        "entry": signal.get("entry"),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
    }
    payload = json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def generate_signal(symbol: str, timeframe: str, candles: List[Candle]) -> dict:
    now_fields = timestamp_fields(candles[-1].time if candles else None)

    if len(candles) < 2:
        return {
            **now_fields,
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

    signal = {
        **timestamp_fields(last.time),
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
    signal["signal_id"] = make_signal_id(signal)
    return signal


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
    if raw_candles and candle.time and str(raw_candles[-1].get("time")) == str(candle.time):
        raw_candles[-1] = candle_dict
    else:
        raw_candles.append(candle_dict)

    raw_candles = raw_candles[-MAX_STORED_CANDLES:]
    state[key] = raw_candles
    save_state(state)
    return [Candle(**item) for item in raw_candles]


def register_open_signal(signal: dict) -> None:
    if signal.get("action") not in {"BUY", "SELL"}:
        return
    if signal.get("stop_loss") is None or signal.get("take_profit") is None:
        return

    state = load_state()
    key = _state_key(signal["symbol"], signal["timeframe"])
    open_signals = state.setdefault("_open_signals", {})
    market_signals = open_signals.setdefault(key, [])

    # Não duplica se o TradingView reenviar a mesma barra.
    existing_ids = {item.get("signal_id") for item in market_signals}
    if signal.get("signal_id") in existing_ids:
        save_state(state)
        return

    market_signals.append(signal)
    open_signals[key] = market_signals[-MAX_OPEN_SIGNALS:]
    save_state(state)


def resolve_signal_with_candle(signal: dict, candle: Candle) -> Optional[dict]:
    action = signal.get("action")
    sl = float(signal.get("stop_loss"))
    tp = float(signal.get("take_profit"))

    if action == "BUY":
        hit_tp = candle.high >= tp
        hit_sl = candle.low <= sl
        win_price = tp
        loss_price = sl
    elif action == "SELL":
        hit_tp = candle.low <= tp
        hit_sl = candle.high >= sl
        win_price = tp
        loss_price = sl
    else:
        return None

    if not hit_tp and not hit_sl:
        return None

    if hit_tp and hit_sl:
        if SAME_CANDLE_POLICY == "optimistic":
            result = "WIN"
            hit_price = win_price
            reason = "TP e SL foram tocados no mesmo candle; política optimistic marcou WIN."
        elif SAME_CANDLE_POLICY == "skip":
            result = "INDEFINIDO"
            hit_price = "TP e SL"
            reason = "TP e SL foram tocados no mesmo candle; sem dados intrabar para saber qual veio primeiro."
        else:
            result = "LOSS"
            hit_price = loss_price
            reason = "TP e SL foram tocados no mesmo candle; política conservative marcou LOSS."
    elif hit_tp:
        result = "WIN"
        hit_price = win_price
        reason = "Take Profit foi atingido."
    else:
        result = "LOSS"
        hit_price = loss_price
        reason = "Stop Loss foi atingido."

    return {
        **timestamp_fields(candle.time),
        "result": result,
        "hit_price": hit_price,
        "reason": reason,
        "signal": signal,
        "candle_open": candle.open,
        "candle_high": candle.high,
        "candle_low": candle.low,
        "candle_close": candle.close,
    }


def check_open_signals(symbol: str, timeframe: str, candle: Candle) -> List[dict]:
    if not WIN_LOSS_ALERTS:
        return []

    state = load_state()
    key = _state_key(symbol, timeframe)
    open_signals = state.setdefault("_open_signals", {})
    market_signals = open_signals.get(key, [])
    if not market_signals:
        return []

    still_open = []
    resolved = []
    candle_time = str(candle.time) if candle.time is not None else ""

    for signal in market_signals:
        # Não confirma WIN/LOSS no mesmo candle que gerou o sinal.
        if candle_time and str(signal.get("timestamp_raw")) == candle_time:
            still_open.append(signal)
            continue

        result = resolve_signal_with_candle(signal, candle)
        if result is None:
            still_open.append(signal)
        else:
            resolved.append(result)

    open_signals[key] = still_open
    closed = state.setdefault("_closed_signals", [])
    closed.extend(resolved)
    state["_closed_signals"] = closed[-200:]
    save_state(state)
    return resolved


@app.post("/signal")
def signal(payload: SignalRequest):
    signal_result = generate_signal(payload.symbol, payload.timeframe, payload.candles)
    try:
        maybe_send_signal(signal_result)
        register_open_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc
    return signal_result


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """Recebe candles do TradingView.

    O TradingView às vezes envia o corpo como text/plain, mesmo contendo JSON.
    Por isso o endpoint lê o corpo manualmente e valida depois, evitando o erro 422
    sem detalhes úteis nos logs.
    """
    raw_body = (await request.body()).decode("utf-8", errors="replace").strip()

    try:
        raw_payload = json.loads(raw_body)
        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Webhook recebeu um corpo que não é JSON válido.",
                "received": raw_body[:500],
                "hint": "No alerta do TradingView, use Any alert() function call e não coloque texto comum como mensagem do webhook.",
            },
        ) from exc

    try:
        payload = TradingViewWebhook(**raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "JSON recebido, mas faltam campos do candle ou algum tipo está inválido.",
                "required_fields": ["symbol", "timeframe", "time", "open", "high", "low", "close", "volume"],
                "validation_errors": exc.errors(),
                "received": raw_payload,
            },
        ) from exc

    candle = Candle(
        time=str(payload.time) if payload.time is not None else None,
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
    )

    candles = append_candle(payload.symbol, payload.timeframe, candle)
    resolved_results = check_open_signals(payload.symbol, payload.timeframe, candle)
    signal_result = generate_signal(payload.symbol, payload.timeframe, candles)

    try:
        for result in resolved_results:
            send_telegram(format_result(result))
        maybe_send_signal(signal_result)
        register_open_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc

    return {
        "signal": signal_result,
        "resolved_results": resolved_results,
        "open_signals_count": len(load_state().get("_open_signals", {}).get(_state_key(payload.symbol, payload.timeframe), [])),
    }


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
    open_signals = state.get("_open_signals", {})
    closed_signals = state.get("_closed_signals", [])
    return {
        "state_file": str(STATE_FILE),
        "timezone": BOT_TIMEZONE,
        "win_loss_alerts": WIN_LOSS_ALERTS,
        "same_candle_policy": SAME_CANDLE_POLICY,
        "markets": {key: len(value) for key, value in state.items() if not key.startswith("_")},
        "open_signals": {key: len(value) for key, value in open_signals.items()},
        "closed_signals_count": len(closed_signals),
    }
