from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import os
import statistics
import threading
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, List, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, ValidationError

APP_NAME = "Railway Forex Pro Scalper"
APP_VERSION = "8.2.0"
app = FastAPI(title=APP_NAME, version=APP_VERSION)
STATE_LOCK = threading.Lock()

# =========================
# Configuracao por variaveis
# =========================
STATE_FILE = Path(os.getenv("BOT_STATE_FILE", "bot_state.json"))
SIGNALS_CSV = Path(os.getenv("BOT_SIGNALS_CSV", "signals_log.csv"))
MAX_STORED_CANDLES = int(os.getenv("MAX_STORED_CANDLES", os.getenv("BOT_BARS", "320")))
MAX_CLOSED_RESULTS = int(os.getenv("MAX_CLOSED_RESULTS", "500"))
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "America/Sao_Paulo")
TIME_FORMAT = os.getenv("BOT_TIME_FORMAT", "%d/%m/%Y %H:%M:%S")

# Telegram
BOT_TELEGRAM = os.getenv("BOT_TELEGRAM", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_PARSE_MODE = os.getenv("TELEGRAM_PARSE_MODE", "HTML")
BOT_STARTUP_ALERT = os.getenv("BOT_STARTUP_ALERT", "true").lower() == "true"
SEND_HOLD_SIGNALS = os.getenv("SEND_HOLD_SIGNALS", "false").lower() == "true"

# Estrategia
STRATEGY_NAME = os.getenv("STRATEGY_NAME", "Pro Scalper v8.2 Prime DD-Controlled M5 - EMA/ADX/MTF/Edge Schedule")
EMA_FAST = int(os.getenv("EMA_FAST", "9"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "21"))
EMA_TREND = int(os.getenv("EMA_TREND", "75"))
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
BREAKOUT_LOOKBACK = int(os.getenv("BREAKOUT_LOOKBACK", "8"))
CHOP_PERIOD = int(os.getenv("CHOP_PERIOD", "14"))

SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "9"))
SCORE_DIFF_MIN = int(os.getenv("SCORE_DIFF_MIN", "2"))
MIN_ADX = float(os.getenv("MIN_ADX", "10"))
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.00004"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "0.006"))
MIN_EMA_SEPARATION_PCT = float(os.getenv("MIN_EMA_SEPARATION_PCT", "0.00002"))
MAX_CHOP = float(os.getenv("MAX_CHOP", "65"))
MIN_VOLUME_MULT = float(os.getenv("MIN_VOLUME_MULT", "1.05"))
MIN_BODY_RATIO = float(os.getenv("MIN_BODY_RATIO", "0.35"))
MAX_CANDLE_ATR_MULT = float(os.getenv("MAX_CANDLE_ATR_MULT", "2.4"))
# v8: filtros extras calibrados no backtest M5 2025
DI_RATIO_MIN = float(os.getenv("DI_RATIO_MIN", "1.0"))
RSI_BUY_LOW = float(os.getenv("RSI_BUY_LOW", "50"))
RSI_BUY_HIGH = float(os.getenv("RSI_BUY_HIGH", "80"))
RSI_SELL_LOW = float(os.getenv("RSI_SELL_LOW", "38"))
RSI_SELL_HIGH = float(os.getenv("RSI_SELL_HIGH", "55"))
PULLBACK_ATR_MULT = float(os.getenv("PULLBACK_ATR_MULT", "0.35"))
MAX_DIST_FROM_EMA_ATR = float(os.getenv("MAX_DIST_FROM_EMA_ATR", "1.25"))
ALLOW_BREAKOUT_SETUP = os.getenv("ALLOW_BREAKOUT_SETUP", "true").lower() == "true"
ALLOW_LIQUIDITY_SWEEP_SETUP = os.getenv("ALLOW_LIQUIDITY_SWEEP_SETUP", "true").lower() == "true"
STRICT_ENTRY_MODE = os.getenv("STRICT_ENTRY_MODE", "true").lower() == "true"
MACD_REQUIRE_HIST_SLOPE = os.getenv("MACD_REQUIRE_HIST_SLOPE", "false").lower() == "true"
EMA_SLOPE_BARS = int(os.getenv("EMA_SLOPE_BARS", "5"))
RECOMMENDED_TIMEFRAME = os.getenv("RECOMMENDED_TIMEFRAME", "M5")
MAX_BARS_IN_SIGNAL = int(os.getenv("MAX_BARS_IN_SIGNAL", "5"))
TIMEOUT_CLOSE_AS_RESULT = os.getenv("TIMEOUT_CLOSE_AS_RESULT", "true").lower() == "true"

# Risco / alvo
ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "0.85"))
ATR_TAKE_MULT = float(os.getenv("ATR_TAKE_MULT", "0.765"))
MIN_STOP_PIPS = float(os.getenv("MIN_STOP_PIPS", "4"))
MAX_STOP_PIPS = float(os.getenv("MAX_STOP_PIPS", "22"))
MIN_STOP_XAU_PIPS = float(os.getenv("MIN_STOP_XAU_PIPS", "18"))
MAX_STOP_XAU_PIPS = float(os.getenv("MAX_STOP_XAU_PIPS", "120"))
ENTRY_ZONE_ATR_MULT = float(os.getenv("ENTRY_ZONE_ATR_MULT", "0.18"))
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "1000"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "2.0"))
PIP_VALUE_PER_LOT_USD = float(os.getenv("PIP_VALUE_PER_LOT_USD", "10"))
MIN_LOT = float(os.getenv("MIN_LOT", "0.01"))
MAX_LOT = float(os.getenv("MAX_LOT", "5"))
LOT_STEP = float(os.getenv("LOT_STEP", "0.01"))

# Filtros profissionais
SESSION_FILTER_ENABLED = os.getenv("SESSION_FILTER_ENABLED", "true").lower() == "true"
# Padrao em UTC: Londres inicial + overlap Londres/NY. Ajuste no Railway se operar outro ativo/horario.
SESSION_WINDOWS_UTC = os.getenv("SESSION_WINDOWS_UTC", "06:00-18:00")
BLOCK_WEEKEND = os.getenv("BLOCK_WEEKEND", "true").lower() == "true"
SYMBOL_ALLOWLIST = [s.strip().upper().replace("/", "") for s in os.getenv("SYMBOL_ALLOWLIST", "EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,AUDUSD,NZDUSD,XAUUSD").split(",") if s.strip()]
SPREAD_UNKNOWN_POLICY = os.getenv("SPREAD_UNKNOWN_POLICY", "ignore").lower()  # ignore | block
MAX_SPREAD_PIPS = float(os.getenv("MAX_SPREAD_PIPS", "1.6"))
MAX_SPREAD_XAU_PIPS = float(os.getenv("MAX_SPREAD_XAU_PIPS", "35"))
NEWS_BLACKOUT_ENABLED = os.getenv("NEWS_BLACKOUT_ENABLED", "false").lower() == "true"
NEWS_BLACKOUT_WINDOWS_UTC = os.getenv("NEWS_BLACKOUT_WINDOWS_UTC", "")  # ex: 2026-05-10T12:25/2026-05-10T13:05;...
BLOCK_HIGH_IMPACT_FLAG = os.getenv("BLOCK_HIGH_IMPACT_FLAG", "true").lower() == "true"

MULTI_TIMEFRAME_CONFIRMATION = os.getenv("MULTI_TIMEFRAME_CONFIRMATION", "true").lower() == "true"
MTF_FACTOR = int(os.getenv("MTF_FACTOR", "3"))
COOLDOWN_BARS = int(os.getenv("COOLDOWN_BARS", "0"))
ALLOW_MULTIPLE_OPEN_SIGNALS = os.getenv("ALLOW_MULTIPLE_OPEN_SIGNALS", "false").lower() == "true"
MAX_OPEN_SIGNALS = int(os.getenv("MAX_OPEN_SIGNALS", "50"))
MAX_OPEN_SIGNALS_PER_MARKET = int(os.getenv("MAX_OPEN_SIGNALS_PER_MARKET", "1"))
MAX_TOTAL_OPEN_SIGNALS = int(os.getenv("MAX_TOTAL_OPEN_SIGNALS", "2"))

# v8.2: filtro de edge por ativo/hora UTC/dia da semana.
# Dias: 0=segunda, 1=terca, 2=quarta, 3=quinta, 4=sexta.
EDGE_SCHEDULE_FILTER_ENABLED = os.getenv("EDGE_SCHEDULE_FILTER_ENABLED", "true").lower() == "true"
EDGE_ALLOWED_HOURS_UTC = os.getenv("EDGE_ALLOWED_HOURS_UTC", "EURUSD:6,7,10,12,13,15|GBPUSD:9,10,11,12|XAUUSD:8,10,12,13,16")
EDGE_ALLOWED_WEEKDAYS_UTC = os.getenv("EDGE_ALLOWED_WEEKDAYS_UTC", "EURUSD:0,1,3|GBPUSD:3,4|XAUUSD:0,1,2,4")
WIN_LOSS_ALERTS = os.getenv("WIN_LOSS_ALERTS", "true").lower() == "true"
SAME_CANDLE_POLICY = os.getenv("SAME_CANDLE_POLICY", "conservative").lower()  # conservative | optimistic | skip
ENABLE_ADMIN_ENDPOINTS = os.getenv("ENABLE_ADMIN_ENDPOINTS", "false").lower() == "true"


class Candle(BaseModel):
    model_config = ConfigDict(extra="allow")
    time: Optional[Union[str, int, float]] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0
    bid: Optional[float] = None
    ask: Optional[float] = None


class SignalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    candles: List[Candle]


class TradingViewWebhook(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    time: Optional[Union[str, int, float]] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0
    bid: Optional[float] = None
    ask: Optional[float] = None
    news: Optional[bool] = False
    impact: Optional[str] = None


# =========================
# Utilitarios
# =========================
def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def parse_tradingview_payload(raw_body: str) -> dict:
    """Aceita JSON normal ou o formato simples key=value;key=value.

    O formato key=value evita erros do Pine Editor mobile com chaves { } e
    str.format(). Mantemos JSON por compatibilidade com versões anteriores.
    """
    raw_body = (raw_body or "").strip()
    if not raw_body:
        raise ValueError("corpo vazio")

    # 1) JSON objeto: {"symbol":"EURUSD", ...}
    # 2) JSON string contendo outro JSON: "{...}"
    try:
        payload = json.loads(raw_body)
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    # 3) Fallback ultra-compativel: symbol=EURUSD;timeframe=1;open=...
    parsed: dict[str, Any] = {}
    for part in raw_body.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key:
            parsed[key] = value

    if not parsed:
        raise ValueError("formato nao reconhecido")

    # Normalizacao dos campos numericos esperados pelo Pydantic.
    for key in ["time", "open", "high", "low", "close", "volume", "bid", "ask"]:
        if key in parsed and parsed[key] not in ("", None):
            try:
                parsed[key] = float(str(parsed[key]).replace(",", "."))
            except Exception:
                # time pode vir como string em alguns ativos; deixa o Pydantic/fluxo lidar.
                pass

    # Campos booleanos opcionais.
    if "news" in parsed:
        parsed["news"] = str(parsed["news"]).lower() in {"1", "true", "yes", "sim"}

    return parsed


def norm_symbol(symbol: str) -> str:
    return str(symbol or "").upper().replace("/", "").replace(".", "").strip()


def get_bot_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(BOT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def parse_timestamp(value: Optional[Union[str, int, float]]) -> datetime:
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
    # TradingView normalmente manda time em milissegundos Unix.
    if number > 10_000_000_000:
        number = number / 1000.0
    return datetime.fromtimestamp(number, tz=timezone.utc)


def timestamp_fields(value: Optional[Union[str, int, float]]) -> dict:
    dt_utc = parse_timestamp(value)
    dt_local = dt_utc.astimezone(get_bot_timezone())
    tz_key = getattr(get_bot_timezone(), "key", "UTC")
    return {
        "timestamp_raw": str(value) if value is not None else None,
        "timestamp_utc": dt_utc.isoformat(),
        "timestamp_local": dt_local.strftime(TIME_FORMAT),
        "timezone": tz_key,
        "timestamp_display": f"{dt_local.strftime(TIME_FORMAT)} ({tz_key})",
    }


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(default if value is None else value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def valid(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def pip_size(symbol: str, price: float) -> float:
    s = norm_symbol(symbol)
    if "JPY" in s:
        return 0.01
    if s.startswith("XAU") or "GOLD" in s:
        return 0.1
    return 0.0001 if price < 20 else 0.01


def max_spread_for_symbol(symbol: str) -> float:
    s = norm_symbol(symbol)
    return MAX_SPREAD_XAU_PIPS if s.startswith("XAU") or "GOLD" in s else MAX_SPREAD_PIPS


def round_price(value: Optional[float], symbol: str, price: float) -> Optional[float]:
    if value is None:
        return None
    if "JPY" in norm_symbol(symbol):
        return round(float(value), 3)
    if norm_symbol(symbol).startswith("XAU") or price >= 100:
        return round(float(value), 2)
    return round(float(value), 5)


def parse_hhmm(raw: str) -> time:
    hour, minute = raw.split(":", 1)
    return time(int(hour), int(minute), tzinfo=timezone.utc)


def in_daily_windows(dt_utc: datetime, windows_raw: str) -> tuple[bool, str]:
    if not windows_raw.strip():
        return True, "sem janela configurada"
    now_t = dt_utc.timetz().replace(second=0, microsecond=0)
    for part in windows_raw.split(","):
        if "-" not in part:
            continue
        start_raw, end_raw = [x.strip() for x in part.split("-", 1)]
        start = parse_hhmm(start_raw)
        end = parse_hhmm(end_raw)
        if start <= end:
            inside = start <= now_t <= end
        else:
            inside = now_t >= start or now_t <= end
        if inside:
            return True, f"dentro da janela UTC {start_raw}-{end_raw}"
    return False, f"fora das janelas UTC {windows_raw}"




def parse_symbol_int_map(raw: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for block in str(raw or "").split("|"):
        block = block.strip()
        if not block or ":" not in block:
            continue
        sym, values = block.split(":", 1)
        nums: set[int] = set()
        for item in values.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                nums.add(int(item))
            except ValueError:
                continue
        if nums:
            out[norm_symbol(sym)] = nums
    return out


def edge_schedule_ok(symbol: str, dt_utc: datetime) -> tuple[bool, str]:
    if not EDGE_SCHEDULE_FILTER_ENABLED:
        return True, "edge schedule desativado"
    sym = norm_symbol(symbol)
    hours_map = parse_symbol_int_map(EDGE_ALLOWED_HOURS_UTC)
    weekdays_map = parse_symbol_int_map(EDGE_ALLOWED_WEEKDAYS_UTC)
    allowed_hours = hours_map.get(sym)
    allowed_weekdays = weekdays_map.get(sym)
    hour_ok = True if allowed_hours is None else dt_utc.hour in allowed_hours
    weekday_ok = True if allowed_weekdays is None else dt_utc.weekday() in allowed_weekdays
    reason = f"hora UTC {dt_utc.hour:02d}:00 {'ok' if hour_ok else 'bloqueada'}; dia {dt_utc.weekday()} {'ok' if weekday_ok else 'bloqueado'}"
    return bool(hour_ok and weekday_ok), reason


def total_open_signals_count(state: dict) -> int:
    return sum(len(v) for v in state.get("_open_signals", {}).values())

def in_news_blackout(dt_utc: datetime) -> tuple[bool, str]:
    if not NEWS_BLACKOUT_ENABLED or not NEWS_BLACKOUT_WINDOWS_UTC.strip():
        return False, "sem blackout de noticias"
    for raw in NEWS_BLACKOUT_WINDOWS_UTC.split(";"):
        raw = raw.strip()
        if "/" not in raw:
            continue
        start_raw, end_raw = raw.split("/", 1)
        try:
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
        if start <= dt_utc <= end:
            return True, f"blackout de noticia UTC {start.isoformat()} -> {end.isoformat()}"
    return False, "fora do blackout de noticias"


def timeframe_to_minutes(tf: str) -> int:
    raw = str(tf or "M1").upper().strip()
    raw = raw.replace("MIN", "").replace("M", "") if raw.startswith("M") else raw
    if raw.endswith("H"):
        return int(raw[:-1] or "1") * 60
    if raw.endswith("D"):
        return int(raw[:-1] or "1") * 1440
    try:
        return max(1, int(raw))
    except Exception:
        return 1


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
            out.append(max(0.0, highs[i] - lows[i]))
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
        if not valid(tr) or not tr:
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
    return wilder_smooth(dx, period), plus_di, minus_di


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


def choppiness_last(highs: List[float], lows: List[float], closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    trs = true_ranges(highs, lows, closes)[-period:]
    high_max = max(highs[-period:])
    low_min = min(lows[-period:])
    denom = high_max - low_min
    if denom <= 0:
        return 100.0
    return 100.0 * math.log10(sum(trs) / denom) / math.log10(period)


def aggregate_candles(candles: List[Candle], factor: int) -> List[Candle]:
    if factor <= 1:
        return candles[:]
    usable = candles[-(len(candles) // factor) * factor :]
    out: List[Candle] = []
    for i in range(0, len(usable), factor):
        chunk = usable[i : i + factor]
        if len(chunk) < factor:
            continue
        out.append(
            Candle(
                time=chunk[-1].time,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(safe_float(c.volume) for c in chunk),
                bid=chunk[-1].bid,
                ask=chunk[-1].ask,
            )
        )
    return out


def htf_bias(candles: List[Candle], symbol: str) -> dict:
    if not MULTI_TIMEFRAME_CONFIRMATION:
        return {"enabled": False, "bias": "NEUTRO", "reason": "MTF desativado"}
    htf = aggregate_candles(candles, MTF_FACTOR)
    if len(htf) < EMA_TREND + 3:
        return {"enabled": True, "bias": "NEUTRO", "reason": f"historico MTF insuficiente {len(htf)}/{EMA_TREND + 3}"}
    closes = [safe_float(c.close) for c in htf]
    ef = ema_values(closes, EMA_FAST)
    es = ema_values(closes, EMA_SLOW)
    et = ema_values(closes, EMA_TREND)
    close = closes[-1]
    if close > float(et[-1] or close) and float(ef[-1] or close) > float(es[-1] or close) > float(et[-1] or close):
        return {"enabled": True, "bias": "BUY", "close": round_price(close, symbol, close), "ema_fast": round_price(ef[-1], symbol, close), "ema_slow": round_price(es[-1], symbol, close), "ema_trend": round_price(et[-1], symbol, close), "reason": f"M{timeframe_to_minutes('1') * MTF_FACTOR} alinhado para compra"}
    if close < float(et[-1] or close) and float(ef[-1] or close) < float(es[-1] or close) < float(et[-1] or close):
        return {"enabled": True, "bias": "SELL", "close": round_price(close, symbol, close), "ema_fast": round_price(ef[-1], symbol, close), "ema_slow": round_price(es[-1], symbol, close), "ema_trend": round_price(et[-1], symbol, close), "reason": f"timeframe agregado x{MTF_FACTOR} alinhado para venda"}
    return {"enabled": True, "bias": "NEUTRO", "close": round_price(close, symbol, close), "reason": "timeframe agregado sem alinhamento claro"}


def score_bar(score: int, threshold: int) -> str:
    total = max(threshold + 4, 10)
    filled = min(total, max(0, score))
    return "█" * filled + "░" * (total - filled)


# =========================
# Estado e estatisticas
# =========================
def state_key(symbol: str, timeframe: str) -> str:
    return f"{norm_symbol(symbol)}::{str(timeframe).upper()}"


def load_state_unlocked() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_state() -> dict:
    with STATE_LOCK:
        return load_state_unlocked()


def save_state_unlocked(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def append_csv(row: dict) -> None:
    try:
        SIGNALS_CSV.parent.mkdir(parents=True, exist_ok=True)
        exists = SIGNALS_CSV.exists()
        fields = [
            "event", "timestamp_utc", "symbol", "timeframe", "signal_id", "action", "result", "entry", "stop_loss", "take_profit",
            "hit_price", "risk_pips", "reward_pips", "rr_estimate", "confidence", "quality", "buy_score", "sell_score",
            "score_diff", "reason",
        ]
        with SIGNALS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception:
        # Log em arquivo nao pode quebrar o webhook.
        pass


def market_open_signals(state: dict, symbol: str, timeframe: str) -> list[dict]:
    return state.get("_open_signals", {}).get(state_key(symbol, timeframe), [])


def append_candle(symbol: str, timeframe: str, candle: Candle) -> List[Candle]:
    with STATE_LOCK:
        state = load_state_unlocked()
        key = state_key(symbol, timeframe)
        raw_candles = state.get(key, [])
        candle_dict = model_to_dict(candle)
        # TradingView pode reenviar/atualizar a mesma barra.
        if raw_candles and candle.time and str(raw_candles[-1].get("time")) == str(candle.time):
            raw_candles[-1] = candle_dict
        else:
            raw_candles.append(candle_dict)
        raw_candles = raw_candles[-MAX_STORED_CANDLES:]
        state[key] = raw_candles
        save_state_unlocked(state)
        return [Candle(**item) for item in raw_candles]


def record_webhook_event(status: str, raw_body: str, parsed: Optional[dict] = None, error: Optional[Any] = None) -> None:
    """Guarda o ultimo webhook recebido para facilitar debug no Railway.

    Importante: webhook invalido agora retorna 200/ignored para nao poluir os logs
    do Railway com 400 infinito, mas fica registrado em /webhook/debug.
    """
    try:
        now = datetime.now(timezone.utc)
        event = {
            "status": status,
            "timestamp_utc": now.isoformat(),
            "received": (raw_body or "")[:1200],
            "parsed": parsed or None,
            "error": str(error)[:1200] if error is not None else None,
        }
        with STATE_LOCK:
            state = load_state_unlocked()
            state["_last_webhook"] = event
            if status != "ok":
                invalid = state.setdefault("_invalid_webhooks", [])
                invalid.append(event)
                state["_invalid_webhooks"] = invalid[-30:]
            save_state_unlocked(state)
    except Exception:
        pass


def cooldown_ok(state: dict, symbol: str, timeframe: str, candle_time: Optional[str]) -> tuple[bool, str]:
    if COOLDOWN_BARS <= 0:
        return True, "cooldown desativado"
    key = state_key(symbol, timeframe)
    last_signals = state.get("_last_signal_bar", {})
    last_raw = last_signals.get(key)
    candles = state.get(key, [])
    if not last_raw or not candles:
        return True, "sem sinal anterior"
    # Conta quantas barras apareceram desde o candle do ultimo sinal.
    recent_times = [str(c.get("time")) for c in candles[-(COOLDOWN_BARS + 2):] if c.get("time") is not None]
    if str(last_raw) in recent_times:
        return False, f"cooldown ativo: aguardar {COOLDOWN_BARS} candles apos o ultimo sinal"
    return True, "cooldown liberado"


def register_open_signal(signal: dict) -> None:
    if signal.get("action") not in {"BUY", "SELL"}:
        return
    if signal.get("stop_loss") is None or signal.get("take_profit") is None:
        return
    with STATE_LOCK:
        state = load_state_unlocked()
        open_signals = state.setdefault("_open_signals", {})
        key = state_key(signal["symbol"], signal["timeframe"])
        market = open_signals.setdefault(key, [])
        existing_ids = {x.get("signal_id") for x in market}
        if signal.get("signal_id") not in existing_ids:
            market.append(signal)
        if not ALLOW_MULTIPLE_OPEN_SIGNALS:
            market = market[-MAX_OPEN_SIGNALS_PER_MARKET:]
        else:
            market = market[-MAX_OPEN_SIGNALS:]
        open_signals[key] = market
        state.setdefault("_last_signal_bar", {})[key] = signal.get("timestamp_raw")
        history = state.setdefault("_signal_history", [])
        if signal.get("signal_id") not in {x.get("signal_id") for x in history[-100:]}:
            history.append(signal)
        state["_signal_history"] = history[-300:]
        save_state_unlocked(state)
    append_csv({"event": "signal", **signal})


def resolve_signal_with_candle(signal: dict, candle: Candle) -> Optional[dict]:
    action = signal.get("action")
    sl = safe_float(signal.get("stop_loss"))
    tp = safe_float(signal.get("take_profit"))
    if action == "BUY":
        hit_tp = candle.high >= tp
        hit_sl = candle.low <= sl
        win_price, loss_price = tp, sl
    elif action == "SELL":
        hit_tp = candle.low <= tp
        hit_sl = candle.high >= sl
        win_price, loss_price = tp, sl
    else:
        return None
    if not hit_tp and not hit_sl:
        return None
    if hit_tp and hit_sl:
        if SAME_CANDLE_POLICY == "optimistic":
            result, hit_price, reason = "WIN", win_price, "TP e SL tocados no mesmo candle; politica optimistic marcou WIN."
        elif SAME_CANDLE_POLICY == "skip":
            result, hit_price, reason = "INDEFINIDO", "TP e SL", "TP e SL tocados no mesmo candle; sem dados intrabar para saber qual veio primeiro."
        else:
            result, hit_price, reason = "LOSS", loss_price, "TP e SL tocados no mesmo candle; politica conservative marcou LOSS."
    elif hit_tp:
        result, hit_price, reason = "WIN", win_price, "Take Profit atingido."
    else:
        result, hit_price, reason = "LOSS", loss_price, "Stop Loss atingido."
    return {
        **timestamp_fields(candle.time),
        "result": result,
        "hit_price": hit_price,
        "reason": reason,
        "signal": signal,
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "signal_id": signal.get("signal_id"),
        "action": action,
        "entry": signal.get("entry"),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "candle_open": candle.open,
        "candle_high": candle.high,
        "candle_low": candle.low,
        "candle_close": candle.close,
    }



def bars_elapsed_for_signal(state: dict, symbol: str, timeframe: str, signal: dict) -> int:
    key = state_key(symbol, timeframe)
    candles = state.get(key, [])
    target = str(signal.get("timestamp_raw"))
    if not target or not candles:
        return 0
    times = [str(c.get("time")) for c in candles if c.get("time") is not None]
    try:
        pos = times.index(target)
        return max(0, len(times) - pos - 1)
    except ValueError:
        return 0


def resolve_signal_timeout(signal: dict, candle: Candle, bars_elapsed: int) -> Optional[dict]:
    if MAX_BARS_IN_SIGNAL <= 0 or bars_elapsed < MAX_BARS_IN_SIGNAL:
        return None
    action = signal.get("action")
    entry = safe_float(signal.get("entry"))
    close = safe_float(candle.close)
    if action == "BUY":
        is_win = close > entry
    elif action == "SELL":
        is_win = close < entry
    else:
        return None
    result = "WIN" if (TIMEOUT_CLOSE_AS_RESULT and is_win) else "LOSS"
    return {
        **timestamp_fields(candle.time),
        "result": result,
        "hit_price": round_price(close, signal.get("symbol", ""), close),
        "reason": f"Sinal expirou apos {bars_elapsed} candles sem TP/SL. Fechamento {'favoravel' if is_win else 'desfavoravel'}.",
        "signal": signal,
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "signal_id": signal.get("signal_id"),
        "action": action,
        "entry": signal.get("entry"),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "candle_open": candle.open,
        "candle_high": candle.high,
        "candle_low": candle.low,
        "candle_close": candle.close,
        "bars_elapsed": bars_elapsed,
    }

def check_open_signals(symbol: str, timeframe: str, candle: Candle) -> List[dict]:
    if not WIN_LOSS_ALERTS:
        return []
    with STATE_LOCK:
        state = load_state_unlocked()
        key = state_key(symbol, timeframe)
        open_signals = state.setdefault("_open_signals", {})
        market = open_signals.get(key, [])
        if not market:
            return []
        still_open: list[dict] = []
        resolved: list[dict] = []
        candle_time = str(candle.time) if candle.time is not None else ""
        for sig in market:
            if candle_time and str(sig.get("timestamp_raw")) == candle_time:
                still_open.append(sig)
                continue
            result = resolve_signal_with_candle(sig, candle)
            if result is None:
                bars_elapsed = bars_elapsed_for_signal(state, symbol, timeframe, sig)
                result = resolve_signal_timeout(sig, candle, bars_elapsed)
            if result is None:
                still_open.append(sig)
            else:
                resolved.append(result)
        open_signals[key] = still_open
        closed = state.setdefault("_closed_signals", [])
        closed.extend(resolved)
        state["_closed_signals"] = closed[-MAX_CLOSED_RESULTS:]
        save_state_unlocked(state)
    for result in resolved:
        append_csv({"event": "result", **result})
    return resolved


def compute_stats() -> dict:
    state = load_state()
    closed = state.get("_closed_signals", [])
    results = [x for x in closed if x.get("result") in {"WIN", "LOSS"}]
    wins = sum(1 for x in results if x.get("result") == "WIN")
    losses = sum(1 for x in results if x.get("result") == "LOSS")
    total = wins + losses
    wr = round((wins / total) * 100, 2) if total else 0.0
    open_count = sum(len(v) for v in state.get("_open_signals", {}).values())
    by_market: dict[str, dict[str, Any]] = {}
    for x in results:
        key = state_key(x.get("symbol", ""), x.get("timeframe", ""))
        stats = by_market.setdefault(key, {"wins": 0, "losses": 0, "total": 0, "win_rate": 0.0})
        stats["wins"] += 1 if x.get("result") == "WIN" else 0
        stats["losses"] += 1 if x.get("result") == "LOSS" else 0
        stats["total"] += 1
    for stats in by_market.values():
        stats["win_rate"] = round((stats["wins"] / stats["total"]) * 100, 2) if stats["total"] else 0.0
    return {
        "signals_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate": wr,
        "open_signals": open_count,
        "markets": {k: len(v) for k, v in state.items() if not k.startswith("_") and isinstance(v, list)},
        "by_market": by_market,
    }


# =========================
# Motor de sinal
# =========================
def build_hold(symbol: str, timeframe: str, candle: Optional[Candle], reason: str, candles_count: int, metrics: Optional[dict] = None) -> dict:
    fields = timestamp_fields(candle.time if candle else None)
    price = safe_float(candle.close) if candle else 0.0
    signal = {
        **fields,
        "strategy": STRATEGY_NAME,
        "version": APP_VERSION,
        "symbol": norm_symbol(symbol),
        "timeframe": str(timeframe).upper(),
        "action": "HOLD",
        "reason": reason,
        "reasons": [reason],
        "entry": round_price(price, symbol, price) if candle else None,
        "entry_zone": None,
        "stop_loss": None,
        "take_profit": None,
        "rr_estimate": None,
        "confidence": 0,
        "quality": "Sem sinal",
        "buy_score": 0,
        "sell_score": 0,
        "score_diff": 0,
        "score_threshold": SCORE_THRESHOLD,
        "candles_count": candles_count,
        "filters": {},
        "metrics": metrics or {},
        "risk": {},
        "management": {},
    }
    signal["signal_id"] = make_signal_id(signal)
    return signal


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
    return hashlib.sha256(payload).hexdigest()[:14]


def risk_block(entry: float, sl: float, tp: float, symbol: str) -> dict:
    pip = pip_size(symbol, entry)
    risk_pips = abs(entry - sl) / pip
    reward_pips = abs(tp - entry) / pip
    risk_amount = ACCOUNT_BALANCE * (RISK_PER_TRADE_PCT / 100.0)
    raw_lot = risk_amount / max(0.000001, risk_pips * PIP_VALUE_PER_LOT_USD)
    stepped = math.floor(raw_lot / LOT_STEP) * LOT_STEP if LOT_STEP > 0 else raw_lot
    lot = min(MAX_LOT, max(MIN_LOT, stepped)) if risk_pips > 0 else 0
    return {
        "account_balance": round(ACCOUNT_BALANCE, 2),
        "risk_pct": RISK_PER_TRADE_PCT,
        "risk_amount": round(risk_amount, 2),
        "risk_pips": round(risk_pips, 1),
        "reward_pips": round(reward_pips, 1),
        "estimated_lot": round(lot, 2),
        "pip_value_per_lot_usd": PIP_VALUE_PER_LOT_USD,
        "note": "Lote estimado; ajuste ao contrato/pip value da sua corretora, especialmente em XAUUSD e contas que nao usam USD.",
    }


def generate_signal(symbol: str, timeframe: str, candles: List[Candle], payload_flags: Optional[dict] = None) -> dict:
    symbol = norm_symbol(symbol)
    timeframe = str(timeframe or "M1").upper()
    if not candles:
        return build_hold(symbol, timeframe, None, "Aguardando candles", 0)

    last = candles[-1]
    last_dt = parse_timestamp(last.time)
    min_bars = max(
        EMA_TREND + 5,
        MACD_SLOW + MACD_SIGNAL + 5,
        ATR_PERIOD * 2 + 5,
        ADX_PERIOD * 2 + 5,
        BB_PERIOD + 5,
        VWAP_PERIOD + 5,
        VOLUME_PERIOD + 5,
        BREAKOUT_LOOKBACK + 5,
        CHOP_PERIOD + 5,
        (EMA_TREND + 5) * MTF_FACTOR if MULTI_TIMEFRAME_CONFIRMATION else 0,
    )
    if len(candles) < min_bars:
        return build_hold(symbol, timeframe, last, f"Aguardando historico minimo: {len(candles)}/{min_bars} candles", len(candles))

    opens = [safe_float(c.open) for c in candles]
    highs = [safe_float(c.high) for c in candles]
    lows = [safe_float(c.low) for c in candles]
    closes = [safe_float(c.close) for c in candles]
    volumes = [safe_float(c.volume) for c in candles]
    close, open_, high, low = closes[-1], opens[-1], highs[-1], lows[-1]
    if close <= 0 or high < low:
        return build_hold(symbol, timeframe, last, "Candle invalido recebido", len(candles))

    ema_fast = ema_values(closes, EMA_FAST)
    ema_slow = ema_values(closes, EMA_SLOW)
    ema_trend = ema_values(closes, EMA_TREND)
    rsi_series = rsi_values(closes, RSI_PERIOD)
    atr_series = atr_values(highs, lows, closes, ATR_PERIOD)
    adx_series, plus_di_series, minus_di_series = adx_values(highs, lows, closes, ADX_PERIOD)
    macd_fast = ema_values(closes, MACD_FAST)
    macd_slow = ema_values(closes, MACD_SLOW)
    macd_line = [float(f or 0.0) - float(s or 0.0) for f, s in zip(macd_fast, macd_slow)]
    macd_signal = ema_values(macd_line, MACD_SIGNAL)
    macd_hist = [m - float(sig or 0.0) for m, sig in zip(macd_line, macd_signal)]
    vwap_series = rolling_vwap(highs, lows, closes, volumes, VWAP_PERIOD)
    vol_ma_series = volume_ma_values(volumes, VOLUME_PERIOD)
    bb_mid, bb_upper, bb_lower = bollinger_last(closes, BB_PERIOD, BB_STD)
    chop = choppiness_last(highs, lows, closes, CHOP_PERIOD)
    mtf = htf_bias(candles, symbol)

    idx, prev = -1, -2
    slope_prev = -1 - max(1, EMA_SLOPE_BARS)
    atr_val = float(atr_series[idx] or 0.0)
    atr_pct_raw = atr_val / close if close else 0.0
    pip = pip_size(symbol, close)
    spread_pips = None
    if last.bid is not None and last.ask is not None:
        spread_pips = max(0.0, (safe_float(last.ask) - safe_float(last.bid)) / pip)
    spread_limit = max_spread_for_symbol(symbol)
    spread_ok = True if spread_pips is None and SPREAD_UNKNOWN_POLICY != "block" else (spread_pips is not None and spread_pips <= spread_limit)

    session_ok, session_reason = in_daily_windows(last_dt, SESSION_WINDOWS_UTC) if SESSION_FILTER_ENABLED else (True, "filtro de sessao desativado")
    edge_ok, edge_reason = edge_schedule_ok(symbol, last_dt)
    symbol_ok = not SYMBOL_ALLOWLIST or symbol in SYMBOL_ALLOWLIST
    weekend_ok = True
    if BLOCK_WEEKEND:
        # Forex costuma fechar no fim de semana; mantém Domingo 22:00 UTC+ liberado para abertura semanal.
        if last_dt.weekday() == 5 or (last_dt.weekday() == 6 and last_dt.hour < 21):
            weekend_ok = False
    blackout, blackout_reason = in_news_blackout(last_dt)
    high_impact_flag = bool(payload_flags and (payload_flags.get("news") or str(payload_flags.get("impact", "")).upper() in {"HIGH", "RED", "ALTO"}))
    news_ok = (not blackout) and not (BLOCK_HIGH_IMPACT_FLAG and high_impact_flag)

    ef = float(ema_fast[idx] or close)
    es = float(ema_slow[idx] or close)
    et = float(ema_trend[idx] or close)
    ef_prev = float(ema_fast[slope_prev] or ef)
    es_prev = float(ema_slow[slope_prev] or es)
    vwap = float(vwap_series[idx] or close)
    rsi_val = float(rsi_series[idx] or 50.0)
    adx_val = float(adx_series[idx] or 0.0)
    plus_di = float(plus_di_series[idx] or 0.0)
    minus_di = float(minus_di_series[idx] or 0.0)
    macd_val = float(macd_line[idx])
    macd_sig = float(macd_signal[idx] or 0.0)
    hist = float(macd_hist[idx])
    hist_prev = float(macd_hist[prev])
    vol = volumes[idx]
    vol_ma = float(vol_ma_series[idx] or 0.0)

    body = abs(close - open_)
    candle_range = max(high - low, 1e-12)
    body_ratio = body / candle_range
    current_range_atr = candle_range / atr_val if atr_val else 99.0
    lookback_high = max(highs[-BREAKOUT_LOOKBACK - 1 : -1])
    lookback_low = min(lows[-BREAKOUT_LOOKBACK - 1 : -1])
    prev_lookback_high = max(highs[-BREAKOUT_LOOKBACK - 2 : -2])
    prev_lookback_low = min(lows[-BREAKOUT_LOOKBACK - 2 : -2])

    volume_available = max(volumes[-VOLUME_PERIOD:]) > 0
    volume_ok = (not volume_available) or (vol_ma <= 0) or (vol >= vol_ma * MIN_VOLUME_MULT)
    volatility_ok = MIN_ATR_PCT <= atr_pct_raw <= MAX_ATR_PCT
    ema_sep_ok = abs(ef - es) / close >= MIN_EMA_SEPARATION_PCT
    chop_ok = (chop is None) or chop <= MAX_CHOP
    spike_ok = current_range_atr <= MAX_CANDLE_ATR_MULT
    if symbol.startswith("XAU") or "GOLD" in symbol:
        stop_min = MIN_STOP_XAU_PIPS * pip
        stop_max = MAX_STOP_XAU_PIPS * pip
    else:
        stop_min = MIN_STOP_PIPS * pip
        stop_max = MAX_STOP_PIPS * pip

    trend_up = close > et and ef > es > et
    trend_down = close < et and ef < es < et
    ema_slope_up = ef > ef_prev and es > es_prev
    ema_slope_down = ef < ef_prev and es < es_prev
    vwap_up = close > vwap
    vwap_down = close < vwap
    rsi_buy = RSI_BUY_LOW <= rsi_val <= RSI_BUY_HIGH
    rsi_sell = RSI_SELL_LOW <= rsi_val <= RSI_SELL_HIGH
    macd_buy = macd_val > macd_sig and hist > 0 and ((not MACD_REQUIRE_HIST_SLOPE) or hist >= hist_prev)
    macd_sell = macd_val < macd_sig and hist < 0 and ((not MACD_REQUIRE_HIST_SLOPE) or hist <= hist_prev)
    adx_buy = adx_val >= MIN_ADX and plus_di > minus_di * DI_RATIO_MIN
    adx_sell = adx_val >= MIN_ADX and minus_di > plus_di * DI_RATIO_MIN
    bull_candle = close > open_ and body_ratio >= MIN_BODY_RATIO
    bear_candle = close < open_ and body_ratio >= MIN_BODY_RATIO
    breakout_buy = close > lookback_high
    breakout_sell = close < lookback_low
    pullback_buy = ((low <= ef + atr_val * PULLBACK_ATR_MULT) or (low <= es + atr_val * PULLBACK_ATR_MULT)) and bull_candle and close > ef
    pullback_sell = ((high >= ef - atr_val * PULLBACK_ATR_MULT) or (high >= es - atr_val * PULLBACK_ATR_MULT)) and bear_candle and close < ef
    liquidity_sweep_buy = low < prev_lookback_low and close > prev_lookback_low and bull_candle
    liquidity_sweep_sell = high > prev_lookback_high and close < prev_lookback_high and bear_candle
    bb_buy = bb_mid is not None and bb_upper is not None and float(bb_mid) <= close <= float(bb_upper)
    bb_sell = bb_mid is not None and bb_lower is not None and float(bb_lower) <= close <= float(bb_mid)
    overextended_buy = rsi_val > 72 or (bb_upper is not None and close > float(bb_upper) and rsi_val > 68)
    overextended_sell = rsi_val < 28 or (bb_lower is not None and close < float(bb_lower) and rsi_val < 32)
    distance_ok = (abs(close - es) / atr_val <= MAX_DIST_FROM_EMA_ATR) if atr_val else False
    structure_buy = pullback_buy or (ALLOW_BREAKOUT_SETUP and breakout_buy) or (ALLOW_LIQUIDITY_SWEEP_SETUP and liquidity_sweep_buy)
    structure_sell = pullback_sell or (ALLOW_BREAKOUT_SETUP and breakout_sell) or (ALLOW_LIQUIDITY_SWEEP_SETUP and liquidity_sweep_sell)
    mtf_buy_ok = mtf.get("bias") == "BUY" if MULTI_TIMEFRAME_CONFIRMATION else True
    mtf_sell_ok = mtf.get("bias") == "SELL" if MULTI_TIMEFRAME_CONFIRMATION else True

    current_metrics = {
        "ema_fast": round_price(ef, symbol, close),
        "ema_slow": round_price(es, symbol, close),
        "ema_trend": round_price(et, symbol, close),
        "vwap": round_price(vwap, symbol, close),
        "rsi": round(rsi_val, 2),
        "macd": round(macd_val, 6),
        "macd_signal": round(macd_sig, 6),
        "macd_hist": round(hist, 6),
        "adx": round(adx_val, 2),
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "atr": round_price(atr_val, symbol, close),
        "atr_pct": round(atr_pct_raw * 100.0, 4),
        "bb_mid": round_price(bb_mid, symbol, close) if bb_mid is not None else None,
        "bb_upper": round_price(bb_upper, symbol, close) if bb_upper is not None else None,
        "bb_lower": round_price(bb_lower, symbol, close) if bb_lower is not None else None,
        "choppiness": round(chop, 2) if chop is not None else None,
        "body_ratio": round(body_ratio, 3),
        "candle_range_atr": round(current_range_atr, 2),
        "volume": round(vol, 2),
        "volume_ma": round(vol_ma, 2),
        "spread_pips": round(spread_pips, 2) if spread_pips is not None else None,
        "mtf": mtf,
    }

    filters = {
        "symbol_ok": symbol_ok,
        "session_ok": session_ok,
        "session_reason": session_reason,
        "edge_schedule_ok": edge_ok,
        "edge_schedule_reason": edge_reason,
        "edge_allowed_hours_utc": EDGE_ALLOWED_HOURS_UTC,
        "edge_allowed_weekdays_utc": EDGE_ALLOWED_WEEKDAYS_UTC,
        "weekend_ok": weekend_ok,
        "news_ok": news_ok,
        "news_reason": blackout_reason if blackout else ("payload marcou noticia de alto impacto" if high_impact_flag else "ok"),
        "spread_ok": spread_ok,
        "spread_pips": current_metrics["spread_pips"],
        "spread_limit_pips": spread_limit,
        "volatility_ok": volatility_ok,
        "ema_separation_ok": ema_sep_ok,
        "chop_ok": chop_ok,
        "spike_ok": spike_ok,
        "volume_ok": volume_ok,
        "distance_ok": distance_ok,
        "structure_buy": structure_buy,
        "structure_sell": structure_sell,
        "recommended_timeframe": RECOMMENDED_TIMEFRAME,
    }

    state = load_state()
    can_cooldown, cooldown_reason = cooldown_ok(state, symbol, timeframe, str(last.time) if last.time is not None else None)
    filters["cooldown_ok"] = can_cooldown
    filters["cooldown_reason"] = cooldown_reason
    current_open_count = len(market_open_signals(state, symbol, timeframe))
    current_total_open_count = total_open_signals_count(state)
    open_ok = ALLOW_MULTIPLE_OPEN_SIGNALS or current_open_count < MAX_OPEN_SIGNALS_PER_MARKET
    total_open_ok = current_total_open_count < MAX_TOTAL_OPEN_SIGNALS
    filters["open_signal_ok"] = open_ok
    filters["open_signals_market"] = current_open_count
    filters["total_open_signal_ok"] = total_open_ok
    filters["open_signals_total"] = current_total_open_count
    filters["max_total_open_signals"] = MAX_TOTAL_OPEN_SIGNALS

    hard_filters = [symbol_ok, session_ok, edge_ok, weekend_ok, news_ok, spread_ok, volatility_ok, ema_sep_ok, chop_ok, spike_ok, distance_ok, can_cooldown, open_ok, total_open_ok]
    if not all(hard_filters):
        failed = [k for k, v in filters.items() if k.endswith("_ok") and v is False and k != "volume_ok"]
        hold = build_hold(symbol, timeframe, last, "Filtro bloqueou sinal: " + ", ".join(failed), len(candles), current_metrics)
        hold["filters"] = filters
        hold["signal_id"] = make_signal_id(hold)
        return hold

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
        add_buy(2, "tendencia EMA alinhada")
    if trend_down:
        add_sell(2, "tendencia EMA alinhada")
    if ema_slope_up:
        add_buy(1, "EMAs inclinadas para cima")
    if ema_slope_down:
        add_sell(1, "EMAs inclinadas para baixo")
    if vwap_up:
        add_buy(1, "preco acima da VWAP")
    if vwap_down:
        add_sell(1, "preco abaixo da VWAP")
    if mtf.get("bias") == "BUY":
        add_buy(2, "timeframe superior confirma compra")
        sell_score -= 1
        sell_reasons.append("-1 MTF contra venda")
    elif mtf.get("bias") == "SELL":
        add_sell(2, "timeframe superior confirma venda")
        buy_score -= 1
        buy_reasons.append("-1 MTF contra compra")
    if rsi_buy:
        add_buy(1, "RSI com momentum comprador sem sobrecompra")
    if rsi_sell:
        add_sell(1, "RSI com momentum vendedor sem sobrevenda")
    if macd_buy:
        add_buy(1, "MACD/histograma comprador")
    if macd_sell:
        add_sell(1, "MACD/histograma vendedor")
    if adx_buy:
        add_buy(1, "ADX com +DI dominante")
    if adx_sell:
        add_sell(1, "ADX com -DI dominante")
    if volume_available and volume_ok:
        add_buy(1, "volume acima da media")
        add_sell(1, "volume acima da media")
    if bull_candle:
        add_buy(1, "candle comprador com corpo relevante")
    if bear_candle:
        add_sell(1, "candle vendedor com corpo relevante")
    if structure_buy:
        add_buy(2, "estrutura de entrada v8.1: pullback/breakout/sweep aprovado")
    if structure_sell:
        add_sell(2, "estrutura de entrada v8.1: pullback/breakout/sweep aprovado")
    if liquidity_sweep_buy:
        add_buy(1, "varredura de liquidez abaixo e fechamento de recuperacao")
    if liquidity_sweep_sell:
        add_sell(1, "varredura de liquidez acima e fechamento de rejeicao")
    if bb_buy:
        add_buy(1, "zona saudavel da Bollinger para compra")
    if bb_sell:
        add_sell(1, "zona saudavel da Bollinger para venda")
    if overextended_buy:
        buy_score -= 2
        buy_reasons.append("-2 compra esticada/sobrecomprada")
    if overextended_sell:
        sell_score -= 2
        sell_reasons.append("-2 venda esticada/sobrevendida")

    diff = buy_score - sell_score
    action = "HOLD"
    reason = "Sem confluencia suficiente para sinal de qualidade"
    selected_score = max(buy_score, sell_score)
    selected_reasons = buy_reasons if buy_score >= sell_score else sell_reasons
    if STRICT_ENTRY_MODE:
        buy_bias_ok = trend_up and ema_slope_up and mtf_buy_ok and adx_buy and rsi_buy and macd_buy and structure_buy
        sell_bias_ok = trend_down and ema_slope_down and mtf_sell_ok and adx_sell and rsi_sell and macd_sell and structure_sell
    else:
        buy_bias_ok = (trend_up or (vwap_up and ef > es and close > et)) and mtf.get("bias") in {"BUY", "NEUTRO"}
        sell_bias_ok = (trend_down or (vwap_down and ef < es and close < et)) and mtf.get("bias") in {"SELL", "NEUTRO"}

    if buy_score >= SCORE_THRESHOLD and diff >= SCORE_DIFF_MIN and buy_bias_ok and not overextended_buy:
        action = "BUY"
        reason = "Setup BUY por tendencia, liquidez, momentum e MTF"
        selected_reasons = buy_reasons
        selected_score = buy_score
    elif sell_score >= SCORE_THRESHOLD and -diff >= SCORE_DIFF_MIN and sell_bias_ok and not overextended_sell:
        action = "SELL"
        reason = "Setup SELL por tendencia, liquidez, momentum e MTF"
        selected_reasons = sell_reasons
        selected_score = sell_score

    if action == "HOLD":
        signal = build_hold(symbol, timeframe, last, reason, len(candles), current_metrics | {"filters": filters})
        signal.update({
            "buy_score": int(buy_score),
            "sell_score": int(sell_score),
            "score_diff": int(diff),
            "reasons": selected_reasons[:10],
            "filters": filters,
        })
        signal["signal_id"] = make_signal_id(signal)
        return signal

    stop_distance = min(max(atr_val * ATR_STOP_MULT, stop_min), stop_max)
    if action == "BUY":
        entry = safe_float(last.ask, close) if last.ask is not None else close
        sl = entry - stop_distance
        tp = entry + max(stop_distance * (ATR_TAKE_MULT / ATR_STOP_MULT), atr_val * ATR_TAKE_MULT)
        zone_low = entry - atr_val * ENTRY_ZONE_ATR_MULT
        zone_high = entry + atr_val * ENTRY_ZONE_ATR_MULT
    else:
        entry = safe_float(last.bid, close) if last.bid is not None else close
        sl = entry + stop_distance
        tp = entry - max(stop_distance * (ATR_TAKE_MULT / ATR_STOP_MULT), atr_val * ATR_TAKE_MULT)
        zone_low = entry - atr_val * ENTRY_ZONE_ATR_MULT
        zone_high = entry + atr_val * ENTRY_ZONE_ATR_MULT

    risk = risk_block(entry, sl, tp, symbol)
    rr = round(risk["reward_pips"] / risk["risk_pips"], 2) if risk.get("risk_pips") else None
    quality = "Institucional" if selected_score >= SCORE_THRESHOLD + 4 else "Alta" if selected_score >= SCORE_THRESHOLD + 2 else "Media"
    confidence = min(96, max(58, int(44 + selected_score * 4 + abs(diff) * 3 + min(adx_val, 40) * 0.25 - max(0, (chop or 0) - 45) * 0.15)))
    management = {
        "partial_take": "Opcional: realizar parcial em +1R se seu plano permitir.",
        "breakeven": "Opcional: mover SL para entrada apos +1R ou rompimento estrutural confirmado.",
        "invalidate": "Cancelar se o candle seguinte fechar contra VWAP/EMA21 antes da entrada.",
        "do_not_chase": "Nao perseguir entrada se o preco sair da zona de entrada.",
    }

    signal = {
        **timestamp_fields(last.time),
        "strategy": STRATEGY_NAME,
        "version": APP_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "reason": reason,
        "reasons": selected_reasons[:10],
        "entry": round_price(entry, symbol, close),
        "entry_zone": {"low": round_price(zone_low, symbol, close), "high": round_price(zone_high, symbol, close)},
        "stop_loss": round_price(sl, symbol, close),
        "take_profit": round_price(tp, symbol, close),
        "rr_estimate": rr,
        "confidence": confidence,
        "quality": quality,
        "buy_score": int(buy_score),
        "sell_score": int(sell_score),
        "score_diff": int(diff),
        "score_threshold": SCORE_THRESHOLD,
        "candles_count": len(candles),
        "filters": filters,
        "metrics": current_metrics,
        "risk": risk,
        "management": management,
    }
    signal["signal_id"] = make_signal_id(signal)
    return signal


# =========================
# Telegram
# =========================
def telegram_enabled() -> bool:
    return BOT_TELEGRAM and bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


def send_telegram(text: str) -> None:
    if not telegram_enabled():
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": TELEGRAM_PARSE_MODE, "disable_web_page_preview": True},
                timeout=20,
            )
            response.raise_for_status()
            return
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"Telegram falhou: {last_exc}")


def fmt_value(value: Any) -> str:
    return "-" if value is None else str(value)


def format_signal(signal: dict) -> str:
    esc = html.escape
    action = signal.get("action", "HOLD")
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(action, "⚪")
    metrics = signal.get("metrics", {}) or {}
    risk = signal.get("risk", {}) or {}
    filters = signal.get("filters", {}) or {}
    reasons = signal.get("reasons", []) or [signal.get("reason", "-")]
    reasons_text = "\n".join(f"• {esc(str(x))}" for x in reasons[:7])
    direction = "COMPRA" if action == "BUY" else "VENDA" if action == "SELL" else "AGUARDAR"
    return "\n".join([
        f"{emoji} <b>SINAL {esc(direction)}</b> | <b>{esc(signal.get('symbol','-'))}</b> {esc(signal.get('timeframe','-'))}",
        f"<b>{esc(signal.get('strategy', STRATEGY_NAME))}</b>",
        f"ID: <code>{esc(signal.get('signal_id', '-'))}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Qualidade: <b>{esc(signal.get('quality','-'))}</b> | Confiança: <b>{signal.get('confidence',0)}%</b>",
        f"Score: BUY <b>{signal.get('buy_score',0)}</b> / SELL <b>{signal.get('sell_score',0)}</b> | Dif: <b>{signal.get('score_diff',0)}</b>",
        f"BUY  {score_bar(int(signal.get('buy_score', 0)), SCORE_THRESHOLD)}",
        f"SELL {score_bar(int(signal.get('sell_score', 0)), SCORE_THRESHOLD)}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Entrada: <b>{fmt_value(signal.get('entry'))}</b>",
        f"Zona: <b>{fmt_value((signal.get('entry_zone') or {}).get('low'))}</b> → <b>{fmt_value((signal.get('entry_zone') or {}).get('high'))}</b>",
        f"SL: <b>{fmt_value(signal.get('stop_loss'))}</b> | TP: <b>{fmt_value(signal.get('take_profit'))}</b> | RR: <b>{fmt_value(signal.get('rr_estimate'))}</b>",
        f"Risco: <b>{risk.get('risk_pips','-')} pips</b> | Alvo: <b>{risk.get('reward_pips','-')} pips</b> | Lote est.: <b>{risk.get('estimated_lot','-')}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"RSI {metrics.get('rsi','-')} | ADX {metrics.get('adx','-')} | ATR% {metrics.get('atr_pct','-')} | CHOP {metrics.get('choppiness','-')}",
        f"VWAP {metrics.get('vwap','-')} | Spread {metrics.get('spread_pips','n/i')} pips | Sessão: {esc(str(filters.get('session_reason','-')))}",
        f"Filtro edge v8.2: {esc(str(filters.get('edge_schedule_reason','-')))}",
        f"MTF: {esc(str((metrics.get('mtf') or {}).get('bias','-')))} — {esc(str((metrics.get('mtf') or {}).get('reason','-')))}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"<b>Motivos:</b>\n{reasons_text}",
        f"Horário: {esc(signal.get('timestamp_display') or signal.get('timestamp_utc') or '-')}",
        "\n⚠️ Sinal não é ordem automática. Valide spread real e gestão antes de operar.",
    ])


def format_result(result: dict) -> str:
    esc = html.escape
    status = result.get("result", "UNKNOWN")
    emoji = "✅" if status == "WIN" else "❌" if status == "LOSS" else "⚠️"
    stats = compute_stats()
    return "\n".join([
        f"{emoji} <b>{esc(status)}</b> | <b>{esc(result.get('symbol','-'))}</b> {esc(result.get('timeframe','-'))}",
        f"ID: <code>{esc(result.get('signal_id','-'))}</code>",
        f"Operação: <b>{esc(result.get('action','-'))}</b>",
        f"Entrada: <b>{result.get('entry','-')}</b> | SL: <b>{result.get('stop_loss','-')}</b> | TP: <b>{result.get('take_profit','-')}</b>",
        f"Preço confirmado: <b>{result.get('hit_price','-')}</b>",
        f"Candle: O {result.get('candle_open','-')} / H {result.get('candle_high','-')} / L {result.get('candle_low','-')} / C {result.get('candle_close','-')}",
        f"Motivo: {esc(result.get('reason','-'))}",
        f"Placar: <b>{stats['wins']}W / {stats['losses']}L</b> | WR: <b>{stats['win_rate']}%</b>",
        f"Horário: {esc(result.get('timestamp_display','-'))}",
    ])


def maybe_send_signal(signal: dict) -> None:
    if signal.get("action") == "HOLD" and not SEND_HOLD_SIGNALS:
        return
    send_telegram(format_signal(signal))


# =========================
# API / Dashboard
# =========================
@app.on_event("startup")
def on_startup() -> None:
    if telegram_enabled() and BOT_STARTUP_ALERT:
        try:
            send_telegram(f"✅ <b>{html.escape(APP_NAME)}</b> online\nVersão: <b>{APP_VERSION}</b>\nEstratégia: <b>{html.escape(STRATEGY_NAME)}</b>")
        except Exception:
            pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


@app.get("/api/status")
def api_status() -> dict:
    state = load_state()
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "strategy": STRATEGY_NAME,
        "telegram_enabled": telegram_enabled(),
        "state_file": str(STATE_FILE),
        "csv_log": str(SIGNALS_CSV),
        "settings": {
            "score_threshold": SCORE_THRESHOLD,
            "score_diff_min": SCORE_DIFF_MIN,
            "session_filter_enabled": SESSION_FILTER_ENABLED,
            "session_windows_utc": SESSION_WINDOWS_UTC,
            "multi_timeframe_confirmation": MULTI_TIMEFRAME_CONFIRMATION,
            "mtf_factor": MTF_FACTOR,
            "risk_per_trade_pct": RISK_PER_TRADE_PCT,
            "max_spread_pips": MAX_SPREAD_PIPS,
            "max_spread_xau_pips": MAX_SPREAD_XAU_PIPS,
            "allow_multiple_open_signals": ALLOW_MULTIPLE_OPEN_SIGNALS,
            "max_open_signals_per_market": MAX_OPEN_SIGNALS_PER_MARKET,
            "max_total_open_signals": MAX_TOTAL_OPEN_SIGNALS,
            "edge_schedule_filter_enabled": EDGE_SCHEDULE_FILTER_ENABLED,
            "edge_allowed_hours_utc": EDGE_ALLOWED_HOURS_UTC,
            "edge_allowed_weekdays_utc": EDGE_ALLOWED_WEEKDAYS_UTC,
        },
        "stats": compute_stats(),
        "last_webhook": state.get("_last_webhook"),
        "invalid_webhooks": state.get("_invalid_webhooks", [])[-5:],
        "open_signals": state.get("_open_signals", {}),
        "latest_signals": state.get("_signal_history", [])[-10:],
    }


@app.get("/strategy/status")
def strategy_status() -> dict:
    return api_status()["settings"] | {"strategy": STRATEGY_NAME, "version": APP_VERSION}


@app.get("/stats")
def stats() -> dict:
    return compute_stats()


@app.get("/signals/open")
def signals_open() -> dict:
    return load_state().get("_open_signals", {})


@app.get("/signals/closed")
def signals_closed(limit: int = 50) -> dict:
    return {"closed": load_state().get("_closed_signals", [])[-max(1, min(limit, 200)):], "stats": compute_stats()}


@app.get("/candles/status")
def candles_status() -> dict:
    state = load_state()
    return {
        "markets": {k: len(v) for k, v in state.items() if not k.startswith("_") and isinstance(v, list)},
        "open_signals": {k: len(v) for k, v in state.get("_open_signals", {}).items()},
        "closed_signals_count": len(state.get("_closed_signals", [])),
        "stats": compute_stats(),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    stats = compute_stats()
    state = load_state()
    latest = state.get("_signal_history", [])[-8:][::-1]
    rows = "".join(
        f"<tr><td>{html.escape(x.get('timestamp_local','-'))}</td><td>{html.escape(x.get('symbol','-'))}</td><td>{html.escape(x.get('timeframe','-'))}</td><td>{html.escape(x.get('action','-'))}</td><td>{x.get('confidence',0)}%</td><td>{html.escape(str(x.get('quality','-')))}</td></tr>"
        for x in latest
    ) or "<tr><td colspan='6'>Sem sinais ainda.</td></tr>"
    html_doc = f"""
    <!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{APP_NAME}</title>
    <style>
      body{{margin:0;background:#080d17;color:#e5eefc;font-family:Inter,Arial,sans-serif}} .wrap{{max-width:1100px;margin:0 auto;padding:22px}}
      .hero{{padding:22px;border:1px solid #1d2a44;border-radius:22px;background:linear-gradient(135deg,#101a2d,#08111f);box-shadow:0 18px 60px #0008}}
      h1{{margin:0;font-size:28px}} .muted{{color:#8ea2c6}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:18px 0}}
      .card{{border:1px solid #1d2a44;border-radius:18px;padding:16px;background:#0b1322}} .num{{font-size:28px;font-weight:800}}
      table{{width:100%;border-collapse:collapse;overflow:hidden;border-radius:16px}} th,td{{padding:11px;border-bottom:1px solid #1d2a44;text-align:left}} th{{color:#9fb5db;background:#0b1322}}
      .ok{{color:#62e6a6}} .bad{{color:#ff7a90}} code{{background:#0b1322;padding:2px 6px;border-radius:7px}}
    </style></head><body><div class='wrap'>
      <div class='hero'><h1>⚡ {APP_NAME}</h1><p class='muted'>Versão {APP_VERSION} • {html.escape(STRATEGY_NAME)}</p><p>Status: <span class='ok'>online</span> • Telegram: {'ativo' if telegram_enabled() else 'desativado'} • Estado: <code>{html.escape(str(STATE_FILE))}</code></p></div>
      <div class='grid'>
        <div class='card'><div class='muted'>WIN</div><div class='num ok'>{stats['wins']}</div></div>
        <div class='card'><div class='muted'>LOSS</div><div class='num bad'>{stats['losses']}</div></div>
        <div class='card'><div class='muted'>Win rate</div><div class='num'>{stats['win_rate']}%</div></div>
        <div class='card'><div class='muted'>Sinais abertos</div><div class='num'>{stats['open_signals']}</div></div>
      </div>
      <div class='card'><h2>Últimos sinais</h2><table><thead><tr><th>Hora</th><th>Ativo</th><th>TF</th><th>Ação</th><th>Conf.</th><th>Qualidade</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class='muted'>Endpoints: <code>/health</code> <code>/api/status</code> <code>/webhook/tradingview</code> <code>/telegram/test</code> <code>/webhook/debug</code> <code>/stats</code></p>
    </div></body></html>"""
    return HTMLResponse(html_doc)


@app.post("/signal")
def signal(payload: SignalRequest) -> dict:
    signal_result = generate_signal(payload.symbol, payload.timeframe, payload.candles)
    try:
        maybe_send_signal(signal_result)
        register_open_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc
    return signal_result


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request) -> dict:
    raw_body = (await request.body()).decode("utf-8", errors="replace").strip()

    try:
        raw_payload = parse_tradingview_payload(raw_body)
    except Exception as exc:
        # Retorna 200 para evitar spam de 400 no Railway, mas registra para debug.
        record_webhook_event("ignored_invalid_format", raw_body, error=exc)
        return {
            "status": "ignored",
            "reason": "payload_invalido_ou_vazio",
            "hint": "No TradingView, apague alertas antigos e crie um novo usando o Pine v7.4 com Any alert() function call.",
            "received_preview": raw_body[:300],
        }

    try:
        payload = TradingViewWebhook(**raw_payload)
    except ValidationError as exc:
        record_webhook_event("ignored_validation_error", raw_body, parsed=raw_payload, error=exc)
        return {
            "status": "ignored",
            "reason": "campos_obrigatorios_ausentes_ou_invalidos",
            "required_fields": ["symbol", "timeframe", "time", "open", "high", "low", "close", "volume"],
            "hint": "Confirme se o alerta ativo foi recriado depois de colar o Pine v7.4. Alertas antigos continuam enviando payload antigo.",
            "received_preview": raw_body[:300],
            "parsed": raw_payload,
        }

    record_webhook_event("ok", raw_body, parsed=raw_payload)
    candle = Candle(time=payload.time, open=payload.open, high=payload.high, low=payload.low, close=payload.close, volume=payload.volume, bid=payload.bid, ask=payload.ask)
    candles = append_candle(payload.symbol, payload.timeframe, candle)
    resolved_results = check_open_signals(payload.symbol, payload.timeframe, candle)
    signal_result = generate_signal(payload.symbol, payload.timeframe, candles, payload_flags=model_to_dict(payload))
    try:
        for result in resolved_results:
            send_telegram(format_result(result))
        maybe_send_signal(signal_result)
        register_open_signal(signal_result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar Telegram: {exc}") from exc
    return {"status": "ok", "signal": signal_result, "resolved_results": resolved_results, "stats": compute_stats()}


@app.get("/webhook/debug")
def webhook_debug() -> dict:
    state = load_state()
    return {
        "last_webhook": state.get("_last_webhook"),
        "invalid_webhooks": state.get("_invalid_webhooks", [])[-10:],
        "candles_status": {k: len(v) for k, v in state.items() if not k.startswith("_") and isinstance(v, list)},
    }


@app.post("/telegram/test")
def telegram_test() -> dict:
    if not telegram_enabled():
        raise HTTPException(status_code=400, detail="Telegram desativado. Configure BOT_TELEGRAM=true, TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
    send_telegram(f"✅ <b>{html.escape(APP_NAME)}</b> conectado\nVersão: <b>{APP_VERSION}</b>\nEstratégia: <b>{html.escape(STRATEGY_NAME)}</b>")
    return {"status": "sent"}


@app.post("/admin/clear-state")
def clear_state() -> dict:
    if not ENABLE_ADMIN_ENDPOINTS:
        raise HTTPException(status_code=403, detail="Endpoint administrativo desativado. Configure ENABLE_ADMIN_ENDPOINTS=true apenas se precisar.")
    with STATE_LOCK:
        save_state_unlocked({})
    return {"status": "cleared"}
