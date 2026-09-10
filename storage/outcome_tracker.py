"""
Tracks what actually HAPPENS to every signal the bot sends — not just
that it was sent, but whether price later hit Take Profit 1, hit Stop
Loss, or the setup expired before either happened.

This is what makes the dashboard's "performance" numbers real (based on
actual market data after the fact) rather than just "here's what we
predicted." Logic mirrors backtest/backtester.py so live results are
directly comparable to backtest results.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from aggregator.signal_aggregator import FinalSignal
from strategies.base import Direction

OUTCOMES_PATH = "storage/outcomes.json"
MAX_HOLDING_BARS = 60  # same horizon used in backtest/backtester.py, for apples-to-apples comparison
MAX_STORED_OUTCOMES = 1000


def _load() -> dict:
    if not os.path.exists(OUTCOMES_PATH):
        return {}
    with open(OUTCOMES_PATH, "r") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(OUTCOMES_PATH), exist_ok=True)
    # Keep the file bounded: drop the oldest CLOSED entries first if over the cap.
    entry_keys = [k for k in data if k != "__open_index__"]
    if len(entry_keys) > MAX_STORED_OUTCOMES:
        closed = sorted(
            (k for k in entry_keys if data[k]["status"] != "OPEN"),
            key=lambda k: data[k].get("opened_at", ""),
        )
        for k in closed[: len(entry_keys) - MAX_STORED_OUTCOMES]:
            del data[k]
    with open(OUTCOMES_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _open_index(data: dict) -> dict:
    return data.setdefault("__open_index__", {})


def register_new_signal(signal: FinalSignal) -> None:
    """Start tracking a freshly-notified BUY/SELL signal. If a previous
    signal for this asset+timeframe was still open (e.g. direction
    flipped before it resolved), mark it SUPERSEDED so it doesn't linger
    forever as OPEN."""
    if signal.direction == Direction.NEUTRAL:
        return
    data = _load()
    index = _open_index(data)
    key = f"{signal.asset}::{signal.timeframe}"

    prev_id = index.get(key)
    if prev_id and prev_id in data and data[prev_id]["status"] == "OPEN":
        data[prev_id]["status"] = "SUPERSEDED"
        data[prev_id]["closed_at"] = signal.timestamp

    entry_ref = signal.entry_high if signal.direction == Direction.BUY else signal.entry_low
    data[signal.signal_id] = {
        "signal_id": signal.signal_id,
        "asset": signal.asset,
        "timeframe": signal.timeframe,
        "direction": signal.direction.value,
        "entry_ref": entry_ref,
        "stop_loss": signal.stop_loss,
        "take_profit_1": signal.take_profit_1,
        "take_profit_2": signal.take_profit_2,
        "confidence": signal.confidence,
        "opened_at": signal.timestamp,
        "bars_open": 0,
        "status": "OPEN",
        "closed_at": None,
        "exit_price": None,
        "pnl_pct": None,
    }
    index[key] = signal.signal_id
    _save(data)


def evaluate_open_outcomes(asset: str, timeframe: str, history: pd.DataFrame) -> None:
    """Check every OPEN outcome for this asset/timeframe against the latest
    persisted price history and close out any that hit TP1, SL, or timed out."""
    data = _load()
    changed = False

    for signal_id, outcome in data.items():
        if signal_id == "__open_index__":
            continue
        if outcome["status"] != "OPEN":
            continue
        if outcome["asset"] != asset or outcome["timeframe"] != timeframe:
            continue

        opened_at = pd.to_datetime(outcome["opened_at"], utc=True)
        bars_after = history[history["timestamp"] > opened_at]
        if bars_after.empty:
            continue

        direction = outcome["direction"]
        stop = outcome["stop_loss"]
        tp1 = outcome["take_profit_1"]
        entry_ref = outcome["entry_ref"]

        resolved = False
        for _, bar in bars_after.iterrows():
            if direction == "BUY":
                hit_sl = bar["low"] <= stop
                hit_tp = bar["high"] >= tp1
            else:
                hit_sl = bar["high"] >= stop
                hit_tp = bar["low"] <= tp1

            if hit_sl:
                exit_price = stop
                status = "SL_HIT"
            elif hit_tp:
                exit_price = tp1
                status = "TP1_HIT"
            else:
                continue

            pnl = ((exit_price - entry_ref) / entry_ref) if direction == "BUY" else \
                  ((entry_ref - exit_price) / entry_ref)
            outcome.update({
                "status": status,
                "closed_at": bar["timestamp"].isoformat(),
                "exit_price": round(float(exit_price), 6),
                "pnl_pct": round(pnl * 100, 3),
                "bars_open": len(bars_after),
            })
            resolved = True
            changed = True
            break

        if not resolved:
            outcome["bars_open"] = len(bars_after)
            changed = True
            if len(bars_after) >= MAX_HOLDING_BARS:
                last_price = float(bars_after.iloc[-1]["close"])
                pnl = ((last_price - entry_ref) / entry_ref) if direction == "BUY" else \
                      ((entry_ref - last_price) / entry_ref)
                outcome.update({
                    "status": "EXPIRED",
                    "closed_at": bars_after.iloc[-1]["timestamp"].isoformat(),
                    "exit_price": round(last_price, 6),
                    "pnl_pct": round(pnl * 100, 3),
                })

    if changed:
        _save(data)


def update_open_levels(signal: FinalSignal) -> None:
    """When a STOP_LOSS_UPDATE / TAKE_PROFIT_UPDATE notification fires,
    find the currently-tracked open trade for this asset+timeframe (via
    the open-index, since the new signal object has a fresh random id
    every run) and keep its levels in sync."""
    data = _load()
    index = _open_index(data)
    key = f"{signal.asset}::{signal.timeframe}"
    open_id = index.get(key)
    if not open_id or open_id not in data or data[open_id]["status"] != "OPEN":
        return
    data[open_id]["stop_loss"] = signal.stop_loss
    data[open_id]["take_profit_1"] = signal.take_profit_1
    data[open_id]["take_profit_2"] = signal.take_profit_2
    _save(data)


def all_outcomes() -> list[dict]:
    return [v for k, v in _load().items() if k != "__open_index__"]


def summary_stats() -> dict:
    outcomes = all_outcomes()
    closed = [o for o in outcomes if o["status"] != "OPEN"]
    wins = [o for o in closed if o["status"] == "TP1_HIT"]
    losses = [o for o in closed if o["status"] == "SL_HIT"]
    expired = [o for o in closed if o["status"] == "EXPIRED"]
    open_count = len(outcomes) - len(closed)

    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0
    avg_pnl = (sum(o["pnl_pct"] for o in closed) / len(closed)) if closed else 0.0

    return {
        "total": len(outcomes),
        "open": open_count,
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "expired": len(expired),
        "win_rate": round(win_rate, 1),
        "avg_pnl_pct": round(avg_pnl, 3),
    }
