"""
Market Regime Detection — classifies each bar's environment so the
Strategy Engine can pick the right playbook (trend strategies in a
trend, mean-reversion in a range, and so on).
"""
from __future__ import annotations

from enum import Enum

import pandas as pd


class Regime(str, Enum):
    TRENDING_BULL = "Trending Bull"
    TRENDING_BEAR = "Trending Bear"
    RANGING = "Ranging"
    HIGH_VOLATILITY = "High Volatility / Choppy"


def detect_regime(row: pd.Series) -> Regime:
    adx = row.get("adx_14", 0)
    ema_50 = row.get("ema_50")
    ema_200 = row.get("ema_200")
    close = row.get("close")
    bb_width = row.get("bb_width", 0)
    vol20 = row.get("volatility_20", 0)

    strong_trend = adx >= 22
    trend_up = ema_50 is not None and ema_200 is not None and ema_50 > ema_200 and close > ema_50
    trend_down = ema_50 is not None and ema_200 is not None and ema_50 < ema_200 and close < ema_50

    if strong_trend and trend_up:
        return Regime.TRENDING_BULL
    if strong_trend and trend_down:
        return Regime.TRENDING_BEAR

    # Choppy/high-vol: wide bands + weak trend strength
    if bb_width and vol20 and vol20 > 0 and bb_width > bb_width.__class__(0.06) and adx < 20:
        return Regime.HIGH_VOLATILITY

    return Regime.RANGING


def annotate_regimes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["regime"] = out.apply(detect_regime, axis=1)
    return out
