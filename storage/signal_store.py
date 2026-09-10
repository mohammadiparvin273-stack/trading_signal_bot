"""
Tracks the last-sent signal per (asset, timeframe) so we only notify on:
NEW signal, direction change, SL/TP update, or invalidation — never spam
the same unchanged signal repeatedly.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Optional

from aggregator.signal_aggregator import FinalSignal
from config.settings import SETTINGS


class SignalStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or SETTINGS.signal_store_path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._state = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return {}

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    def _key(self, asset: str, timeframe: str) -> str:
        return f"{asset}::{timeframe}"

    def should_notify(self, sig: FinalSignal) -> tuple[bool, str]:
        """Returns (should_notify, change_type)."""
        key = self._key(sig.asset, sig.timeframe)
        prev = self._state.get(key)

        if sig.direction.value == "NEUTRAL":
            # Only notify NEUTRAL if we previously had an active (non-neutral) signal
            # — i.e. this is effectively an invalidation of a prior call.
            if prev and prev.get("direction") != "NEUTRAL":
                return True, "INVALIDATION"
            return False, "NONE"

        if prev is None:
            return True, "NEW_SIGNAL"

        if prev.get("direction") != sig.direction.value:
            return True, "NEW_SIGNAL"

        # Same direction — check if levels materially changed.
        changed = []
        for field_name in ("stop_loss", "take_profit_1", "take_profit_2"):
            old_v, new_v = prev.get(field_name), getattr(sig, field_name)
            if old_v is None or new_v is None:
                continue
            if abs(float(old_v) - float(new_v)) / max(abs(float(old_v)), 1e-9) > 0.005:
                changed.append(field_name)

        if changed:
            if "stop_loss" in changed:
                return True, "STOP_LOSS_UPDATE"
            return True, "TAKE_PROFIT_UPDATE"

        return False, "NONE"

    def record(self, sig: FinalSignal) -> None:
        key = self._key(sig.asset, sig.timeframe)
        self._state[key] = asdict(sig)
        self._state[key]["direction"] = sig.direction.value
        self._save()
