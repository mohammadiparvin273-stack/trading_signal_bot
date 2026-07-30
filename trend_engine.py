"""
مرحله اول: تشخیص روند بازار (Bullish / Bearish / Sideways)
"""
import pandas as pd


def detect_swing_structure(df: pd.DataFrame, window: int = 5):
    """تشخیص ساده Higher-High/Higher-Low یا Lower-High/Lower-Low با پیوت‌ها."""
    highs = df["high"]
    lows = df["low"]
    pivot_highs, pivot_lows = [], []

    for i in range(window, len(df) - window):
        if highs.iloc[i] == highs.iloc[i - window:i + window + 1].max():
            pivot_highs.append((i, highs.iloc[i]))
        if lows.iloc[i] == lows.iloc[i - window:i + window + 1].min():
            pivot_lows.append((i, lows.iloc[i]))

    structure = "unknown"
    if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
        hh = pivot_highs[-1][1] > pivot_highs[-2][1]
        hl = pivot_lows[-1][1] > pivot_lows[-2][1]
        lh = pivot_highs[-1][1] < pivot_highs[-2][1]
        ll = pivot_lows[-1][1] < pivot_lows[-2][1]
        if hh and hl:
            structure = "bullish"
        elif lh and ll:
            structure = "bearish"
        else:
            structure = "mixed"

    return structure, pivot_highs, pivot_lows


def detect_trend(df: pd.DataFrame) -> dict:
    """
    خروجی: {"trend": "bullish"/"bearish"/"sideways", "adx": float, "score": 0..1}
    قانون: اگر بازار رنج باشد هیچ سیگنالی صادر نمی‌شود.
    """
    last = df.iloc[-1]
    ema50, ema200, adx = last.get("ema50"), last.get("ema200"), last.get("adx")

    if pd.isna(ema50) or pd.isna(ema200) or pd.isna(adx):
        return {"trend": "sideways", "adx": 0, "score": 0}

    structure, _, _ = detect_swing_structure(df)

    is_trending = adx >= 20
    if not is_trending:
        return {"trend": "sideways", "adx": round(float(adx), 2), "score": 0}

    if ema50 > ema200 and structure in ("bullish", "unknown"):
        trend = "bullish"
    elif ema50 < ema200 and structure in ("bearish", "unknown"):
        trend = "bearish"
    else:
        trend = "sideways"

    # امتیاز 0..1 بر اساس قدرت ADX (سقف در 40)
    score = min(adx / 40, 1.0) if trend != "sideways" else 0

    return {"trend": trend, "adx": round(float(adx), 2), "score": round(score, 2)}
