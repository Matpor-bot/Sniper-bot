from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .config import Settings
from .indicators import adx, atr, bollinger_bands, ema, rsi


REQUIRED_COLS = {"open", "high", "low", "close"}


def pip_size(symbol: str, price: float) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if s.startswith("XAU") or "GOLD" in s:
        return 0.1
    return 0.0001 if price < 20 else 0.01


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("No candle data received")

    cols = {c.lower(): c for c in df.columns}
    if not REQUIRED_COLS.issubset(cols):
        raise ValueError(f"Missing required columns: {sorted(REQUIRED_COLS - set(cols))}")

    rename_map = {}
    for key in ["time", "timestamp", "datetime"]:
        if key in cols:
            rename_map[cols[key]] = "time"
            break
    if "volume" in cols:
        rename_map[cols["volume"]] = "volume"
    for key in REQUIRED_COLS:
        if cols[key] != key:
            rename_map[cols[key]] = key

    out = df.rename(columns=rename_map).copy()
    if "time" in out.columns:
        out["time"] = pd.to_datetime(out["time"], errors="coerce", utc=True)
        out = out.sort_values("time")
    out = out.reset_index(drop=True)

    for c in REQUIRED_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=list(REQUIRED_COLS)).reset_index(drop=True)

    if "volume" not in out.columns:
        out["volume"] = 0
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    return out


@dataclass(slots=True)
class SignalEngine:
    settings: Settings

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = normalize_df(df).copy()
        df["ema_fast"] = ema(df["close"], self.settings.ema_fast)
        df["ema_slow"] = ema(df["close"], self.settings.ema_slow)
        df["ema_trend"] = ema(df["close"], self.settings.ema_trend)
        df["rsi"] = rsi(df["close"], self.settings.rsi_period)
        df["atr"] = atr(df, self.settings.atr_period)
        df["bb_mid"], df["bb_upper"], df["bb_lower"] = bollinger_bands(df["close"], self.settings.bb_period, self.settings.bb_std)
        df["adx"] = adx(df, self.settings.adx_period)
        df["body"] = (df["close"] - df["open"]).abs()
        df["range"] = (df["high"] - df["low"]).replace(0, np.nan)
        df["body_ratio"] = (df["body"] / df["range"]).fillna(0.0)
        df["ema_fast_slope"] = df["ema_fast"].diff()
        df["ema_slow_slope"] = df["ema_slow"].diff()
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
        df["vol_ma"] = df["volume"].rolling(20).mean().fillna(df["volume"].mean())
        return df

    def _bar_time(self, row: pd.Series) -> pd.Timestamp:
        if "time" in row and pd.notna(row["time"]):
            ts = pd.Timestamp(row["time"])
            return ts.tz_localize(timezone.utc) if ts.tzinfo is None else ts
        return pd.Timestamp.now(tz=timezone.utc)

    def _spread_pips(self, row: pd.Series, symbol: str) -> float:
        if "bid" in row and "ask" in row and pd.notna(row["bid"]) and pd.notna(row["ask"]):
            return float((row["ask"] - row["bid"]) / pip_size(symbol, float(row["close"])))
        return 0.0

    def score_row(self, row: pd.Series, symbol: str) -> dict:
        close = float(row["close"])
        rsi_val = float(row["rsi"])
        adx_val = float(row["adx"])
        atr_val = float(row["atr"])
        spread_pips = self._spread_pips(row, symbol)

        trend_up = close > float(row["ema_trend"]) and float(row["ema_fast"]) > float(row["ema_slow"]) > float(row["ema_trend"])
        trend_down = close < float(row["ema_trend"]) and float(row["ema_fast"]) < float(row["ema_slow"]) < float(row["ema_trend"])
        slope_up = float(row["ema_fast_slope"]) > 0 and float(row["ema_slow_slope"]) > 0
        slope_down = float(row["ema_fast_slope"]) < 0 and float(row["ema_slow_slope"]) < 0
        bull = float(row["close"]) > float(row["open"]) and float(row["body_ratio"]) >= 0.35
        bear = float(row["close"]) < float(row["open"]) and float(row["body_ratio"]) >= 0.35
        breakout_up = pd.notna(row["prev_high"]) and close > float(row["prev_high"])
        breakout_down = pd.notna(row["prev_low"]) and close < float(row["prev_low"])
        pullback_buy = pd.notna(row["ema_fast"]) and float(row["low"]) <= float(row["ema_fast"]) <= close
        pullback_sell = pd.notna(row["ema_fast"]) and float(row["high"]) >= float(row["ema_fast"]) >= close
        mean_reversion_buy = pd.notna(row["bb_lower"]) and close <= float(row["bb_lower"]) and rsi_val <= 35
        mean_reversion_sell = pd.notna(row["bb_upper"]) and close >= float(row["bb_upper"]) and rsi_val >= 65

        atr_pct = atr_val / close if close else 0.0
        volatility_ok = atr_pct >= self.settings.min_atr_pct
        spread_ok = spread_pips <= self.settings.max_spread_pips
        trend_strength = adx_val >= 18.0

        buy_score = 0
        sell_score = 0

        if trend_up:
            buy_score += 2
        if trend_down:
            sell_score += 2
        if slope_up:
            buy_score += 1
        if slope_down:
            sell_score += 1
        if 52 <= rsi_val <= 72:
            buy_score += 1
        if 28 <= rsi_val <= 48:
            sell_score += 1
        if bull:
            buy_score += 1
        if bear:
            sell_score += 1
        if breakout_up or pullback_buy or mean_reversion_buy:
            buy_score += 1
        if breakout_down or pullback_sell or mean_reversion_sell:
            sell_score += 1
        if trend_strength:
            buy_score += 1
            sell_score += 1
        if not volatility_ok:
            buy_score -= 1
            sell_score -= 1
        if not spread_ok:
            buy_score -= 2
            sell_score -= 2

        return {
            "buy_score": buy_score,
            "sell_score": sell_score,
            "atr": atr_val,
            "rsi": rsi_val,
            "adx": adx_val,
            "spread_pips": spread_pips,
            "atr_pct": atr_pct,
            "volatility_ok": volatility_ok,
            "spread_ok": spread_ok,
            "trend_up": trend_up,
            "trend_down": trend_down,
            "breakout_up": breakout_up,
            "breakout_down": breakout_down,
            "pullback_buy": pullback_buy,
            "pullback_sell": pullback_sell,
            "mean_reversion_buy": mean_reversion_buy,
            "mean_reversion_sell": mean_reversion_sell,
        }

    def generate_signal(self, df: pd.DataFrame, symbol: Optional[str] = None, timeframe: Optional[str] = None) -> dict:
        symbol = symbol or self.settings.symbol
        timeframe = timeframe or self.settings.timeframe
        df = self.prepare(df)
        min_bars = max(self.settings.ema_trend, self.settings.bb_period, self.settings.atr_period, self.settings.adx_period) + 5
        if len(df) < min_bars:
            raise ValueError(f"Need at least {min_bars} candles")

        row = df.iloc[-1]
        stats = self.score_row(row, symbol)
        diff = int(stats["buy_score"] - stats["sell_score"])
        action: str = "HOLD"
        reason = "No strong edge"

        if stats["spread_ok"] and stats["volatility_ok"]:
            if diff >= self.settings.score_threshold and stats["trend_up"]:
                action = "BUY"
                reason = "Trend aligned up + momentum confirmed"
            elif -diff >= self.settings.score_threshold and stats["trend_down"]:
                action = "SELL"
                reason = "Trend aligned down + momentum confirmed"
            elif stats["buy_score"] >= self.settings.score_threshold and (stats["breakout_up"] or stats["pullback_buy"] or stats["mean_reversion_buy"]) and stats["rsi"] >= 45:
                action = "BUY"
                reason = "Breakout/pullback/mean reversion buy setup"
            elif stats["sell_score"] >= self.settings.score_threshold and (stats["breakout_down"] or stats["pullback_sell"] or stats["mean_reversion_sell"]) and stats["rsi"] <= 55:
                action = "SELL"
                reason = "Breakout/pullback/mean reversion sell setup"

        return self._build_result(action, reason, row, stats, diff, symbol, timeframe)

    def _build_result(self, action: str, reason: str, row: pd.Series, stats: dict, diff: int, symbol: str, timeframe: str) -> dict:
        close = float(row["close"])
        atr_val = float(stats["atr"])
        if action == "BUY":
            sl = close - atr_val * self.settings.atr_stop_mult
            tp = close + atr_val * self.settings.atr_take_mult
        elif action == "SELL":
            sl = close + atr_val * self.settings.atr_stop_mult
            tp = close - atr_val * self.settings.atr_take_mult
        else:
            sl = None
            tp = None

        rr = None
        if sl is not None and tp is not None:
            risk = abs(close - sl)
            reward = abs(tp - close)
            rr = round(reward / risk, 2) if risk else None

        confidence = min(95, max(0, 50 + abs(diff) * 10 + (5 if stats["trend_up"] or stats["trend_down"] else 0)))
        ts = self._bar_time(row).isoformat()
        return {
            "timestamp_utc": ts,
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "reason": reason,
            "confidence": confidence,
            "entry": round(close, 6),
            "stop_loss": round(sl, 6) if sl is not None else None,
            "take_profit": round(tp, 6) if tp is not None else None,
            "rr_estimate": rr,
            "buy_score": int(stats["buy_score"]),
            "sell_score": int(stats["sell_score"]),
            "score_diff": diff,
            "rsi": round(float(stats["rsi"]), 2),
            "adx": round(float(stats["adx"]), 2),
            "atr": round(float(stats["atr"]), 6),
            "atr_pct": round(float(stats["atr_pct"]) * 100, 4),
            "spread_pips": round(float(stats["spread_pips"]), 2),
            "trend_up": bool(stats["trend_up"]),
            "trend_down": bool(stats["trend_down"]),
            "volatility_ok": bool(stats["volatility_ok"]),
            "spread_ok": bool(stats["spread_ok"]),
        }
