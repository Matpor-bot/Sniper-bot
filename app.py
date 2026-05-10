from __future__ import annotations

import hashlib
import html
import json
import math
import os
import statistics
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
ALLOW_MULTIPLE_OPEN_SIGNALS = os.getenv("ALLOW_MULTIPLE_OPEN_SIGNALS", "false").lower() == "true"

# Estrategia v6: score de confluencia para scalping.
# Usa filtros muito comuns em setups de scalping: EMA, VWAP, RSI, MACD,
# ADX, ATR, Bollinger Bands, volume e candle de rompimento/pullback.
STRATEGY_NAME = os.getenv("STRATEGY_NAME", "Pro Scalper v6 - EMA/VWAP/RSI/MACD/ADX/ATR")
EMA_FAST = int(os.getenv("EMA_FAST", "9"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "21"))
EMA_TREND = int(os.getenv("EMA_TREND", "50"))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
MACD_FAST = int(os.getenv("MACD_FAST", "12"))
MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ADX_PERIOD = int(os.getenv("ADX_PERIOD", "14"))
BB_PERIOD = int(os.getenv("BB_PERIOD", "20"))
BB_STD = float(os.getenv("BB_STD", "2.0"))
VWAP_PERIOD = int(os.getenv("VWAP_PERIOD", "50"))
VOLUME_PERIOD = int(os.getenv("VOLUME_PERIOD", "20"))
BREAKOUT_LOOKBACK = int(os.getenv("BREAKOUT_LOOKBACK", "5"))
SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "7"))
SCORE_DIFF_MIN = int(os.getenv("SCORE_DIFF_MIN", "2"))
MIN_ADX = float(os.getenv("MIN_ADX", "18"))
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.00025"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "0.025"))
MIN_VOLUME_MULT = float(os.getenv("MIN_VOLUME_MULT", "1.05"))
MIN_BODY_RATIO = float(os.getenv("MIN_BODY_RATIO", "0.35"))
ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "1.2"))
ATR_TAKE_MULT = float(os.getenv("ATR_TAKE_MULT", "1.6"))


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
    return {"status": "online", "strategy": STRATEGY_NAME}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/strategy/status")
def strategy_status():
    return {
        "strategy": STRATEGY_NAME,
        "description": "Sinal por score de confluencia, nao por candle anterior.",
        "score_threshold": SCORE_THRESHOLD,
        "score_diff_min": SCORE_DIFF_MIN,
        "ema_fast": EMA_FAST,
        "ema_slow": EMA_SLOW,
        "ema_trend": EMA_TREND,
        "rsi_period": RSI_PERIOD,
        "macd": {"fast": MACD_FAST, "slow": MACD_SLOW, "signal": MACD_SIGNAL},
        "atr_period": ATR_PERIOD,
        "adx_period": ADX_PERIOD,
        "min_adx": MIN_ADX,
        "min_atr_pct": MIN_ATR_PCT,
        "max_atr_pct": MAX_ATR_PCT,
        "bb_period": BB_PERIOD,
        "bb_std": BB_STD,
        "vwap_period": VWAP_PERIOD,
        "volume_period": VOLUME_PERIOD,
        "min_volume_mult": MIN_VOLUME_MULT,
        "breakout_lookback": BREAKOUT_LOOKBACK,
        "allow_multiple_open_signals": ALLOW_MULTIPLE_OPEN_SIGNALS,
    }


def get_bot_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(BOT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def parse_timestamp(value: Optional[Union[str, int, float]]) -> datetime:
    """Converte timestamp do TradingView para datetime UTC.

    O TradingView costuma enviar `time` em milissegundos Unix, como
    1778376960000. Tambem aceitamos segundos Unix e datas ISO.
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
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)

    if number > 10_000_000_000:
        number = number / 1000.0
    return datetime.fromtimestamp(number, tz=timezone.utc)


def timestamp_fields(value: Optional[Union[str, int, float]]) -> dict:
    dt_utc = parse_timestamp(value)
    dt_local = dt_utc.astimezone(get_bot_timezone())
    tz = BOT_TIMEZONE if get_bot_timezone().key != "UTC" else "UTC"
    return {
        "timestamp_raw": str(value) if value is not None else None,
        "timestamp_utc": dt_utc.isoformat(),
        "timestamp_local": dt_local.strftime(TIME_FORMAT),
        "timezone": tz,
        "timestamp_display": f"{dt_local.strftime(TIME_FORMAT)} ({tz})",
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
    metrics = signal.get("metrics", {}) or {}
    reasons = signal.get("reasons", []) or []
    reasons_text = "; ".join(str(x) for x in reasons[:5]) if reasons else signal.get("reason", "-")

    return "\n".join(
        [
            f"{emoji} <b>{esc(action)}</b> | {esc(signal['symbol'])} {esc(signal['timeframe'])}",
            f"ID: <code>{esc(signal.get('signal_id', '-'))}</code>",
            f"Estrategia: <b>{esc(signal.get('strategy', STRATEGY_NAME))}</b>",
            f"Qualidade: <b>{esc(signal.get('quality', '-'))}</b> | Confianca: <b>{signal.get('confidence', 0)}%</b>",
            f"Score BUY/SELL: <b>{signal.get('buy_score', 0)}/{signal.get('sell_score', 0)}</b>",
            f"Entrada: <b>{signal['entry']}</b>",
            f"Stop Loss: <b>{signal['stop_loss']}</b>",
            f"Take Profit: <b>{signal['take_profit']}</b>",
            f"RR estimado: <b>{signal.get('rr_estimate', '-')}</b>",
            f"Indicadores: RSI {metrics.get('rsi', '-')} | ADX {metrics.get('adx', '-')} | ATR% {metrics.get('atr_pct', '-')} | VWAP {metrics.get('vwap', '-')}",
            f"Motivos: {esc(reasons_text)}",
            f"Horario: {esc(signal.get('timestamp_display') or signal.get('timestamp_utc') or '-')}",
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
            f"Operacao: <b>{esc(signal.get('action', '-'))}</b>",
            f"Entrada: <b>{signal.get('entry', '-')}</b>",
            f"Stop Loss: <b>{signal.get('stop_loss', '-')}</b>",
            f"Take Profit: <b>{signal.get('take_profit', '-')}</b>",
            f"Preco que confirmou: <b>{result.get('hit_price', '-')}</b>",
            f"Candle: O {result.get('candle_open', '-')} / H {result.get('candle_high', '-')} / L {result.get('candle_low', '-')} / C {result.get('candle_close', '-')}",
            f"Horario: {esc(result.get('timestamp_display', '-'))}",
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
        "buy_score": signal.get("buy_score"),
        "sell_score": signal.get("sell_score"),
    }
    payload = json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _safe_float(value: Optional[Union[int, float]]) -> float:
    try:
        out = float(value if value is not None else 0.0)
        return out if math.isfinite(out) else 0.0
    except Exception:
        return 0.0


def _is_valid_number(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(float(value))


def ema_values(values: List[float], period: int) -> List[Optional[float]]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out: List[Optional[float]] = []
    current: Optional[float] = None
    for value in values:
        current = value if current is None else (value * alpha) + (current * (1.0 - alpha))
        out.append(current)
    return out


def sma_last(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def std_last(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    sample = values[-period:]
    mean = sum(sample) / period
    return math.sqrt(sum((x - mean) ** 2 for x in sample) / period)


def rsi_values(closes: List[float], period: int) -> List[Optional[float]]:
    if not closes:
        return []
    out: List[Optional[float]] = [None]
    avg_gain: Optional[float] = None
    avg_loss: Optional[float] = None
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        gains.append(gain)
        losses.append(loss)
        if i < period:
            out.append(None)
            continue
        if i == period:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
        else:
            avg_gain = ((avg_gain or 0.0) * (period - 1) + gain) / period
            avg_loss = ((avg_loss or 0.0) * (period - 1) + loss) / period
        if not avg_loss:
            out.append(100.0)
        else:
            rs = (avg_gain or 0.0) / avg_loss
            out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def true_ranges(highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
    out: List[float] = []
    for i in range(len(closes)):
        if i == 0:
            out.append(highs[i] - lows[i])
        else:
            out.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return out


def wilder_smooth(values: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    current: Optional[float] = None
    for i, value in enumerate(values):
        if i + 1 < period:
            out.append(None)
        elif i + 1 == period:
            current = sum(values[:period]) / period
            out.append(current)
        else:
            current = ((current or 0.0) * (period - 1) + value) / period
            out.append(current)
    return out


def atr_values(highs: List[float], lows: List[float], closes: List[float], period: int) -> List[Optional[float]]:
    return wilder_smooth(true_ranges(highs, lows, closes), period)


def adx_values(highs: List[float], lows: List[float], closes: List[float], period: int) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    tr_smoothed = wilder_smooth(true_ranges(highs, lows, closes), period)
    plus_smoothed = wilder_smooth(plus_dm, period)
    minus_smoothed = wilder_smooth(minus_dm, period)

    plus_di: List[Optional[float]] = []
    minus_di: List[Optional[float]] = []
    dx: List[float] = []
    for tr, plus, minus in zip(tr_smoothed, plus_smoothed, minus_smoothed):
        if not _is_valid_number(tr) or not tr:
            plus_di.append(None)
            minus_di.append(None)
            dx.append(0.0)
            continue
        pdi = 100.0 * float(plus or 0.0) / float(tr)
        mdi = 100.0 * float(minus or 0.0) / float(tr)
        plus_di.append(pdi)
        minus_di.append(mdi)
        denom = pdi + mdi
        dx.append(100.0 * abs(pdi - mdi) / denom if denom else 0.0)

    adx = wilder_smooth(dx, period)
    return adx, plus_di, minus_di


def rolling_vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    typical = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    for i in range(len(closes)):
        start = max(0, i - period + 1)
        vols = volumes[start : i + 1]
        prices = typical[start : i + 1]
        vol_sum = sum(vols)
        if vol_sum > 0:
            out.append(sum(p * v for p, v in zip(prices, vols)) / vol_sum)
        else:
            out.append(sum(closes[start : i + 1]) / len(closes[start : i + 1]))
    return out


def volume_ma_values(volumes: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(volumes)):
        start = max(0, i - period + 1)
        sample = volumes[start : i + 1]
        out.append(sum(sample) / len(sample) if sample else None)
    return out


def bollinger_last(closes: List[float], period: int, std_mult: float) -> tuple[Optional[float], Optional[float], Optional[float]]:
    mid = sma_last(closes, period)
    std = std_last(closes, period)
    if mid is None or std is None:
        return None, None, None
    return mid, mid + std_mult * std, mid - std_mult * std


def latest_open_signals_count(symbol: str, timeframe: str) -> int:
    state = load_state()
    return len(state.get("_open_signals", {}).get(_state_key(symbol, timeframe), []))


def _build_hold(symbol: str, timeframe: str, candle: Optional[Candle], reason: str, candles_count: int, metrics: Optional[dict] = None) -> dict:
    fields = timestamp_fields(candle.time if candle else None)
    entry = round(float(candle.close), 6) if candle else None
    signal = {
        **fields,
        "strategy": STRATEGY_NAME,
        "symbol": symbol,
        "timeframe": timeframe,
        "action": "HOLD",
        "reason": reason,
        "reasons": [reason],
        "entry": entry,
        "stop_loss": None,
        "take_profit": None,
        "rr_estimate": None,
        "confidence": 0,
        "quality": "Sem sinal",
        "buy_score": 0,
        "sell_score": 0,
        "score_diff": 0,
        "metrics": metrics or {},
        "candles_count": candles_count,
    }
    signal["signal_id"] = make_signal_id(signal)
    return signal


def generate_signal(symbol: str, timeframe: str, candles: List[Candle]) -> dict:
    if not candles:
        return _build_hold(symbol, timeframe, None, "Aguardando candles", 0)

    last = candles[-1]
    min_bars = max(EMA_TREND, MACD_SLOW + MACD_SIGNAL, ATR_PERIOD * 2, ADX_PERIOD * 2, BB_PERIOD, VWAP_PERIOD, VOLUME_PERIOD, BREAKOUT_LOOKBACK + 2) + 2
    if len(candles) < min_bars:
        return _build_hold(
            symbol,
            timeframe,
            last,
            f"Aguardando historico minimo para estrategia pro: {len(candles)}/{min_bars} candles",
            len(candles),
        )

    opens = [_safe_float(c.open) for c in candles]
    highs = [_safe_float(c.high) for c in candles]
    lows = [_safe_float(c.low) for c in candles]
    closes = [_safe_float(c.close) for c in candles]
    volumes = [_safe_float(c.volume) for c in candles]

    close = closes[-1]
    open_ = opens[-1]
    high = highs[-1]
    low = lows[-1]
    if close <= 0 or high < low:
        return _build_hold(symbol, timeframe, last, "Candle invalido recebido", len(candles))

    ema_fast = ema_values(closes, EMA_FAST)
    ema_slow = ema_values(closes, EMA_SLOW)
    ema_trend = ema_values(closes, EMA_TREND)
    rsi_series = rsi_values(closes, RSI_PERIOD)
    atr_series = atr_values(highs, lows, closes, ATR_PERIOD)
    adx_series, plus_di_series, minus_di_series = adx_values(highs, lows, closes, ADX_PERIOD)
    macd_fast = ema_values(closes, MACD_FAST)
    macd_slow = ema_values(closes, MACD_SLOW)
    macd_line: List[float] = [float(f or 0.0) - float(s or 0.0) for f, s in zip(macd_fast, macd_slow)]
    macd_signal_series = ema_values(macd_line, MACD_SIGNAL)
    macd_hist = [m - float(sig or 0.0) for m, sig in zip(macd_line, macd_signal_series)]
    vwap_series = rolling_vwap(highs, lows, closes, volumes, VWAP_PERIOD)
    vol_ma_series = volume_ma_values(volumes, VOLUME_PERIOD)
    bb_mid, bb_upper, bb_lower = bollinger_last(closes, BB_PERIOD, BB_STD)

    idx = -1
    prev_idx = -2
    current_metrics = {
        "ema_fast": round(float(ema_fast[idx] or 0.0), 6),
        "ema_slow": round(float(ema_slow[idx] or 0.0), 6),
        "ema_trend": round(float(ema_trend[idx] or 0.0), 6),
        "vwap": round(float(vwap_series[idx] or 0.0), 6),
        "rsi": round(float(rsi_series[idx] or 50.0), 2),
        "macd": round(float(macd_line[idx]), 6),
        "macd_signal": round(float(macd_signal_series[idx] or 0.0), 6),
        "macd_hist": round(float(macd_hist[idx]), 6),
        "adx": round(float(adx_series[idx] or 0.0), 2),
        "plus_di": round(float(plus_di_series[idx] or 0.0), 2),
        "minus_di": round(float(minus_di_series[idx] or 0.0), 2),
        "atr": round(float(atr_series[idx] or 0.0), 6),
        "atr_pct": round(((float(atr_series[idx] or 0.0) / close) * 100.0), 4),
        "bb_mid": round(float(bb_mid or 0.0), 6),
        "bb_upper": round(float(bb_upper or 0.0), 6),
        "bb_lower": round(float(bb_lower or 0.0), 6),
        "volume": round(float(volumes[idx]), 4),
        "volume_ma": round(float(vol_ma_series[idx] or 0.0), 4),
    }

    atr_val = float(atr_series[idx] or 0.0)
    atr_pct_raw = atr_val / close if close else 0.0
    if atr_val <= 0:
        return _build_hold(symbol, timeframe, last, "ATR indisponivel; aguardando mais candles validos", len(candles), current_metrics)
    if atr_pct_raw < MIN_ATR_PCT:
        return _build_hold(symbol, timeframe, last, "Volatilidade baixa: ATR abaixo do minimo configurado", len(candles), current_metrics)
    if atr_pct_raw > MAX_ATR_PCT:
        return _build_hold(symbol, timeframe, last, "Volatilidade extrema: candle/ATR acima do limite de seguranca", len(candles), current_metrics)

    if not ALLOW_MULTIPLE_OPEN_SIGNALS and latest_open_signals_count(symbol, timeframe) > 0:
        return _build_hold(symbol, timeframe, last, "Ja existe sinal aberto nesse ativo/timeframe; aguardando WIN ou LOSS", len(candles), current_metrics)

    body = abs(close - open_)
    candle_range = max(high - low, 1e-12)
    body_ratio = body / candle_range
    bull_candle = close > open_ and body_ratio >= MIN_BODY_RATIO
    bear_candle = close < open_ and body_ratio >= MIN_BODY_RATIO
    lookback_high = max(highs[-BREAKOUT_LOOKBACK - 1 : -1])
    lookback_low = min(lows[-BREAKOUT_LOOKBACK - 1 : -1])

    ef = float(ema_fast[idx] or close)
    es = float(ema_slow[idx] or close)
    et = float(ema_trend[idx] or close)
    ef_prev = float(ema_fast[prev_idx] or ef)
    es_prev = float(ema_slow[prev_idx] or es)
    vwap = float(vwap_series[idx] or close)
    rsi_val = float(rsi_series[idx] or 50.0)
    adx_val = float(adx_series[idx] or 0.0)
    plus_di = float(plus_di_series[idx] or 0.0)
    minus_di = float(minus_di_series[idx] or 0.0)
    macd_val = float(macd_line[idx])
    macd_sig = float(macd_signal_series[idx] or 0.0)
    hist = float(macd_hist[idx])
    hist_prev = float(macd_hist[prev_idx])
    vol = volumes[idx]
    vol_ma = float(vol_ma_series[idx] or 0.0)
    volume_available = max(volumes[-VOLUME_PERIOD:]) > 0
    volume_ok = (not volume_available) or (vol_ma <= 0) or (vol >= vol_ma * MIN_VOLUME_MULT)

    trend_up = close > et and ef > es > et
    trend_down = close < et and ef < es < et
    ema_slope_up = ef > ef_prev and es > es_prev
    ema_slope_down = ef < ef_prev and es < es_prev
    vwap_up = close > vwap
    vwap_down = close < vwap
    rsi_buy = 50 <= rsi_val <= 68
    rsi_sell = 32 <= rsi_val <= 50
    macd_buy = macd_val > macd_sig and hist > 0 and hist >= hist_prev
    macd_sell = macd_val < macd_sig and hist < 0 and hist <= hist_prev
    adx_buy = adx_val >= MIN_ADX and plus_di > minus_di
    adx_sell = adx_val >= MIN_ADX and minus_di > plus_di
    breakout_buy = close > lookback_high
    breakout_sell = close < lookback_low
    pullback_buy = (low <= ef <= close or low <= vwap <= close) and bull_candle and close > es
    pullback_sell = (high >= ef >= close or high >= vwap >= close) and bear_candle and close < es
    bb_buy = bb_mid is not None and bb_upper is not None and float(bb_mid) <= close <= float(bb_upper)
    bb_sell = bb_mid is not None and bb_lower is not None and float(bb_lower) <= close <= float(bb_mid)
    overextended_buy = rsi_val > 72 or (bb_upper is not None and close > float(bb_upper) and rsi_val > 68)
    overextended_sell = rsi_val < 28 or (bb_lower is not None and close < float(bb_lower) and rsi_val < 32)

    buy_score = 0
    sell_score = 0
    buy_reasons: List[str] = []
    sell_reasons: List[str] = []

    def add_buy(points: int, reason: str) -> None:
        nonlocal buy_score
        buy_score += points
        buy_reasons.append(f"+{points} {reason}")

    def add_sell(points: int, reason: str) -> None:
        nonlocal sell_score
        sell_score += points
        sell_reasons.append(f"+{points} {reason}")

    if trend_up:
        add_buy(2, "tendencia de alta por EMA 9/21/50")
    if trend_down:
        add_sell(2, "tendencia de baixa por EMA 9/21/50")
    if ema_slope_up:
        add_buy(1, "EMAs inclinadas para cima")
    if ema_slope_down:
        add_sell(1, "EMAs inclinadas para baixo")
    if vwap_up:
        add_buy(1, "preco acima da VWAP")
    if vwap_down:
        add_sell(1, "preco abaixo da VWAP")
    if rsi_buy:
        add_buy(1, "RSI confirma momentum comprador sem sobrecompra")
    if rsi_sell:
        add_sell(1, "RSI confirma momentum vendedor sem sobrevenda")
    if macd_buy:
        add_buy(1, "MACD/histograma positivo")
    if macd_sell:
        add_sell(1, "MACD/histograma negativo")
    if adx_buy:
        add_buy(1, "ADX mostra tendencia com +DI acima de -DI")
    if adx_sell:
        add_sell(1, "ADX mostra tendencia com -DI acima de +DI")
    if volume_ok:
        if volume_available:
            add_buy(1, "volume acima da media")
            add_sell(1, "volume acima da media")
        else:
            buy_reasons.append("volume nao disponivel; filtro ignorado")
            sell_reasons.append("volume nao disponivel; filtro ignorado")
    if bull_candle:
        add_buy(1, "candle comprador com corpo relevante")
    if bear_candle:
        add_sell(1, "candle vendedor com corpo relevante")
    if breakout_buy or pullback_buy:
        add_buy(1, "rompimento/pullback comprador")
    if breakout_sell or pullback_sell:
        add_sell(1, "rompimento/pullback vendedor")
    if bb_buy:
        add_buy(1, "preco em zona saudavel da Bollinger")
    if bb_sell:
        add_sell(1, "preco em zona saudavel da Bollinger")
    if overextended_buy:
        buy_score -= 2
        buy_reasons.append("-2 compra esticada/sobrecomprada")
    if overextended_sell:
        sell_score -= 2
        sell_reasons.append("-2 venda esticada/sobrevendida")

    diff = buy_score - sell_score
    action = "HOLD"
    selected_score = max(buy_score, sell_score)
    selected_reasons: List[str] = []
    reason = "Sem confluencia suficiente para sinal de qualidade"

    buy_bias_ok = trend_up or (vwap_up and ef > es and close > et)
    sell_bias_ok = trend_down or (vwap_down and ef < es and close < et)

    if buy_score >= SCORE_THRESHOLD and diff >= SCORE_DIFF_MIN and buy_bias_ok and not overextended_buy:
        action = "BUY"
        selected_score = buy_score
        selected_reasons = buy_reasons
        reason = "Setup BUY por confluencia de tendencia, momentum, VWAP e volatilidade"
    elif sell_score >= SCORE_THRESHOLD and -diff >= SCORE_DIFF_MIN and sell_bias_ok and not overextended_sell:
        action = "SELL"
        selected_score = sell_score
        selected_reasons = sell_reasons
        reason = "Setup SELL por confluencia de tendencia, momentum, VWAP e volatilidade"
    else:
        selected_reasons = buy_reasons if buy_score >= sell_score else sell_reasons

    if action == "BUY":
        sl = close - atr_val * ATR_STOP_MULT
        tp = close + atr_val * ATR_TAKE_MULT
    elif action == "SELL":
        sl = close + atr_val * ATR_STOP_MULT
        tp = close - atr_val * ATR_TAKE_MULT
    else:
        sl = None
        tp = None

    rr = None
    if sl is not None and tp is not None:
        risk = abs(close - sl)
        reward = abs(tp - close)
        rr = round(reward / risk, 2) if risk else None

    quality = "Alta" if selected_score >= SCORE_THRESHOLD + 2 else "Media" if action != "HOLD" else "Sem sinal"
    confidence = 0 if action == "HOLD" else min(94, max(55, int(42 + selected_score * 4 + abs(diff) * 3 + min(adx_val, 35.0) * 0.35)))

    signal = {
        **timestamp_fields(last.time),
        "strategy": STRATEGY_NAME,
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "reason": reason,
        "reasons": selected_reasons[:8],
        "entry": round(close, 6),
        "stop_loss": round(sl, 6) if sl is not None else None,
        "take_profit": round(tp, 6) if tp is not None else None,
        "rr_estimate": rr,
        "confidence": confidence,
        "quality": quality,
        "buy_score": int(buy_score),
        "sell_score": int(sell_score),
        "score_diff": int(diff),
        "score_threshold": SCORE_THRESHOLD,
        "candles_count": len(candles),
        "metrics": current_metrics,
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

    # Nao duplica se o TradingView reenviar a mesma barra.
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
            reason = "TP e SL foram tocados no mesmo candle; politica optimistic marcou WIN."
        elif SAME_CANDLE_POLICY == "skip":
            result = "INDEFINIDO"
            hit_price = "TP e SL"
            reason = "TP e SL foram tocados no mesmo candle; sem dados intrabar para saber qual veio primeiro."
        else:
            result = "LOSS"
            hit_price = loss_price
            reason = "TP e SL foram tocados no mesmo candle; politica conservative marcou LOSS."
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
        # Nao confirma WIN/LOSS no mesmo candle que gerou o sinal.
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

    O TradingView as vezes envia o corpo como text/plain, mesmo contendo JSON.
    Por isso o endpoint le o corpo manualmente e valida depois, evitando o erro 422
    sem detalhes uteis nos logs.
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
                "error": "Webhook recebeu um corpo que nao e JSON valido.",
                "received": raw_body[:500],
                "hint": "No alerta do TradingView, use Any alert() function call e nao coloque texto comum como mensagem do webhook.",
            },
        ) from exc

    try:
        payload = TradingViewWebhook(**raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "JSON recebido, mas faltam campos do candle ou algum tipo esta invalido.",
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
        "strategy": STRATEGY_NAME,
        "timezone": BOT_TIMEZONE,
        "win_loss_alerts": WIN_LOSS_ALERTS,
        "same_candle_policy": SAME_CANDLE_POLICY,
        "markets": {key: len(value) for key, value in state.items() if not key.startswith("_")},
        "open_signals": {key: len(value) for key, value in open_signals.items()},
        "closed_signals_count": len(closed_signals),
    }
