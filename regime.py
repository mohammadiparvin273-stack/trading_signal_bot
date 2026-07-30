"""
مرحله ششم: Market Regime
Trend / Range / Volatile
"""
import pandas as pd


def detect_regime(df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    adx = last.get("adx")
    atr = last.get("atr")
    atr_sma = last.get("atr_sma")

    if pd.isna(adx) or pd.isna(atr) or pd.isna(atr_sma):
        return "unknown"

    volatile = atr > atr_sma * 1.8
    if volatile:
        return "volatile"
    if adx >= 20:
        return "trend"
    return "range"
