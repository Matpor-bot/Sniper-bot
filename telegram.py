from __future__ import annotations

import html
import time
from dataclasses import dataclass
from typing import Any, Dict

import requests

from .config import Settings


@dataclass(slots=True)
class TelegramNotifier:
    settings: Settings

    def enabled(self) -> bool:
        return bool(self.settings.telegram_enabled and self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/{method}"

    def _post(self, method: str, payload: Dict[str, Any], retries: int = 3) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(self._api_url(method), json=payload, timeout=20)
                resp.raise_for_status()
                return
            except Exception as exc:  # pragma: no cover - network dependent
                last_exc = exc
                time.sleep(min(2 * attempt, 5))
        raise RuntimeError(f"Telegram request failed: {last_exc}")

    def send_text(self, text: str) -> None:
        if not self.enabled():
            return
        self._post(
            "sendMessage",
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "parse_mode": self.settings.telegram_parse_mode,
                "disable_web_page_preview": True,
            },
        )

    def format_signal(self, signal: Dict[str, Any]) -> str:
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal["action"], "⚪")
        esc = html.escape
        lines = [
            f"{emoji} <b>{esc(signal['action'])}</b> | {esc(signal['symbol'])} {esc(signal['timeframe'])}",
            f"Signal ID: <code>{esc(signal.get('signal_id', '-'))}</code>",
            f"Entry: <b>{signal['entry']}</b>",
            f"SL: <b>{signal['stop_loss']}</b> | TP: <b>{signal['take_profit']}</b>",
            f"Confidence: <b>{signal['confidence']}%</b> | RR: <b>{signal['rr_estimate']}</b>",
            f"RSI: {signal['rsi']} | ADX: {signal['adx']} | ATR%: {signal['atr_pct']}%",
            f"Spread: {signal['spread_pips']} pips",
            f"Reason: {esc(signal['reason'])}",
            f"Time: {esc(signal['timestamp_utc'])}",
        ]
        return "\n".join(lines)

    def send_signal(self, signal: Dict[str, Any]) -> None:
        if not self.enabled():
            return
        self.send_text(self.format_signal(signal))

    def send_startup(self, app_name: str, status: str) -> None:
        if not self.enabled() or not self.settings.telegram_alert_on_startup:
            return
        self.send_text(f"✅ <b>{html.escape(app_name)}</b> online\nStatus: {html.escape(status)}")
