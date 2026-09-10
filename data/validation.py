"""Basic data-quality checks before anything downstream trusts the data."""
from __future__ import annotations

import numpy as np
import pandas as pd


class DataValidationError(Exception):
    pass


def validate_ohlcv(df: pd.DataFrame, min_bars: int = 50) -> pd.DataFrame:
    if df is None or df.empty:
        raise DataValidationError("Empty OHLCV data.")
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise DataValidationError(f"Missing columns: {missing}")

    df = df.copy()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["high"] >= df["low"])]
    df = df[(df["close"] > 0) & (df["open"] > 0)]

    # Remove impossible spikes (>50% single-candle move) — likely bad ticks
    ret = df["close"].pct_change().abs()
    df = df[(ret < 0.5) | (ret.isna())]

    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

    if len(df) < min_bars:
        raise DataValidationError(f"Not enough clean bars: {len(df)} < {min_bars}")

    return df
