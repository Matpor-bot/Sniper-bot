from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

Action = Literal["BUY", "SELL", "HOLD"]


class Candle(BaseModel):
    time: Optional[str] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0
    bid: Optional[float] = None
    ask: Optional[float] = None


class SignalPayload(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    candles: List[Candle]


class SignalResponse(BaseModel):
    timestamp_utc: str
    symbol: str
    timeframe: str
    action: Action
    reason: str
    confidence: int
    entry: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    rr_estimate: Optional[float]
    buy_score: int
    sell_score: int
    score_diff: int
    rsi: float
    adx: float
    atr: float
    atr_pct: float
    spread_pips: float
    trend_up: bool
    trend_down: bool
    volatility_ok: bool
    spread_ok: bool
    signal_id: str
