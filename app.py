
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Scalping Bot")

class Candle(BaseModel):
    time: str | None = None
    open: float
    high: float
    low: float
    close: float
    volume: float | None = 0

class SignalRequest(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    candles: List[Candle]

@app.get("/")
def root():
    return {"status": "online"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/signal")
def signal(payload: SignalRequest):
    candles = payload.candles

    if len(candles) < 2:
        return {
            "action": "HOLD",
            "reason": "Not enough candles"
        }

    last = candles[-1]
    prev = candles[-2]

    action = "BUY" if last.close > prev.close else "SELL"

    return {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe,
        "action": action,
        "entry": last.close,
        "stop_loss": round(last.close * 0.998, 5),
        "take_profit": round(last.close * 1.002, 5),
        "confidence": 72
    }
