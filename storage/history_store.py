"""
Persists OHLCV history to disk (as CSV, one file per symbol+timeframe)
so market data ACCUMULATES across runs instead of being thrown away
every time the process exits (which happens on every GitHub Actions
run — each run starts on a brand-new, empty machine).

This is the file the ML/DL models are actually trained on. In
GitHub Actions, this file is committed back to the repo after every
run, so it grows over time and survives forever.
"""
from __future__ import annotations

import os
import re

import pandas as pd

HISTORY_DIR = "storage/history"
MAX_STORED_ROWS = 6000  # cap per symbol so the repo doesn't grow forever


def _safe_name(symbol: str, timeframe: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", symbol)
    return f"{safe}_{timeframe}.csv"


def history_path(symbol: str, timeframe: str) -> str:
    return os.path.join(HISTORY_DIR, _safe_name(symbol, timeframe))


def load_history(symbol: str, timeframe: str) -> pd.DataFrame:
    path = history_path(symbol, timeframe)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


def save_and_merge(symbol: str, timeframe: str, new_df: pd.DataFrame) -> pd.DataFrame:
    """Merge freshly-fetched candles into the persisted history, dedupe,
    cap to MAX_STORED_ROWS, write back to disk, and return the merged
    DataFrame (this is what gets used for features/ML training)."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    existing = load_history(symbol, timeframe)

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
    merged = merged.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    merged = merged.tail(MAX_STORED_ROWS).reset_index(drop=True)

    merged.to_csv(history_path(symbol, timeframe), index=False)
    return merged


def dataset_info(symbol: str, timeframe: str) -> dict:
    df = load_history(symbol, timeframe)
    if df.empty:
        return {"rows": 0, "from": None, "to": None}
    return {
        "rows": len(df),
        "from": str(df["timestamp"].min()),
        "to": str(df["timestamp"].max()),
    }
