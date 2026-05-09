from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Settings:
    symbol: str = os.getenv("BOT_SYMBOL", "EURUSD")
    timeframe: str = os.getenv("BOT_TIMEFRAME", "M1")
    bars: int = int(os.getenv("BOT_BARS", "300"))

    ema_fast: int = int(os.getenv("EMA_FAST", "9"))
    ema_slow: int = int(os.getenv("EMA_SLOW", "21"))
    ema_trend: int = int(os.getenv("EMA_TREND", "55"))
    rsi_period: int = int(os.getenv("RSI_PERIOD", "7"))
    atr_period: int = int(os.getenv("ATR_PERIOD", "14"))
    bb_period: int = int(os.getenv("BB_PERIOD", "20"))
    bb_std: float = float(os.getenv("BB_STD", "2.0"))
    adx_period: int = int(os.getenv("ADX_PERIOD", "14"))

    min_atr_pct: float = float(os.getenv("MIN_ATR_PCT", "0.00015"))
    max_spread_pips: float = float(os.getenv("MAX_SPREAD_PIPS", "1.5"))
    atr_stop_mult: float = float(os.getenv("ATR_STOP_MULT", "1.15"))
    atr_take_mult: float = float(os.getenv("ATR_TAKE_MULT", "1.55"))
    score_threshold: int = int(os.getenv("SCORE_THRESHOLD", "4"))
    cooldown_bars: int = int(os.getenv("COOLDOWN_BARS", "3"))

    output_json: str = os.getenv("BOT_OUTPUT_JSON", "signals.json")
    output_csv: str = os.getenv("BOT_OUTPUT_CSV", "signals_log.csv")
    state_file: str = os.getenv("BOT_STATE_FILE", "bot_state.json")

    telegram_enabled: bool = os.getenv("BOT_TELEGRAM", "false").lower() == "true"
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_parse_mode: str = os.getenv("TELEGRAM_PARSE_MODE", "HTML")
    telegram_alert_on_startup: bool = os.getenv("BOT_STARTUP_ALERT", "false").lower() == "true"

    mt5_login: Optional[int] = int(os.getenv("MT5_LOGIN", "0") or 0) or None
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
