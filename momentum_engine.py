"""
مرحله پنجم: Momentum Engine
RSI, MACD Histogram, EMA Slope, ATR Expansion
"""
import pandas as pd


def analyze_momentum(df: pd.DataFrame, direction: str) -> dict:
    last = df.iloc[-1]
    prev = df.iloc[-5] if len(df) > 5 else df.iloc[0]

    rsi = last.get("rsi")
    macd_hist = last.get("macd_hist")
    ema20_now = last.get("ema20")
    ema20_prev = prev.get("ema20")
    atr = last.get("atr")
    atr_sma = last.get("atr_sma")

    ema_slope_up = bool(ema20_now and ema20_prev and ema20_now > ema20_prev)
    atr_expansion = bool(atr and atr_sma and atr > atr_sma)

    score = 0.0
    if direction == "bullish":
        if not pd.isna(rsi) and rsi > 50:
            score += 0.3
        if not pd.isna(macd_hist) and macd_hist > 0:
            score += 0.3
        if ema_slope_up:
            score += 0.2
    else:
        if not pd.isna(rsi) and rsi < 50:
            score += 0.3
        if not pd.isna(macd_hist) and macd_hist < 0:
            score += 0.3
        if not ema_slope_up:
            score += 0.2

    if atr_expansion:
        score += 0.2

    score = min(score, 1.0)

    return {
        "rsi": round(float(rsi), 1) if not pd.isna(rsi) else None,
        "macd_hist": round(float(macd_hist), 4) if not pd.isna(macd_hist) else None,
        "ema_slope_up": ema_slope_up,
        "atr_expansion": atr_expansion,
        "score": round(score, 2),
    }
