from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .config import Settings


class StateStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = Path(settings.state_file)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class SignalStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.json_path = Path(settings.output_json)
        self.csv_path = Path(settings.output_csv)
        self.state = StateStore(settings)

    @staticmethod
    def signal_id(signal: Dict[str, Any]) -> str:
        stable = {
            k: signal.get(k)
            for k in [
                "timestamp_utc",
                "symbol",
                "timeframe",
                "action",
                "entry",
                "stop_loss",
                "take_profit",
                "buy_score",
                "sell_score",
                "score_diff",
            ]
        }
        payload = json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def persist(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        signal = dict(signal)
        signal.setdefault("signal_id", self.signal_id(signal))
        self.json_path.write_text(json.dumps(signal, indent=2, ensure_ascii=False), encoding="utf-8")
        df = pd.DataFrame([signal])
        if self.csv_path.exists():
            df.to_csv(self.csv_path, mode="a", header=False, index=False)
        else:
            df.to_csv(self.csv_path, index=False)

        state = self.state.load()
        state["latest_signal"] = signal
        self.state.save(state)
        return signal

    def latest(self) -> Optional[dict]:
        state = self.state.load()
        return state.get("latest_signal")
