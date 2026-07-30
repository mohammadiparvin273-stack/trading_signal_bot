"""
مرحله چهارم: Volume Engine
Relative Volume, Volume Spike, VWAP, Order Book Imbalance
"""
import pandas as pd


def analyze_volume(df: pd.DataFrame, order_book_imbalance: float = 0.0) -> dict:
    last = df.iloc[-1]
    rel_vol = last.get("rel_volume")
    vwap = last.get("vwap")
    close = last["close"]

    if pd.isna(rel_vol):
        rel_vol = 1.0

    volume_spike = bool(rel_vol >= 1.5)
    above_vwap = bool(close > vwap) if not pd.isna(vwap) else None

    # امتیاز 0..1
    score = 0.0
    if volume_spike:
        score += 0.5
    if abs(order_book_imbalance) >= 0.15:
        score += 0.3
    if rel_vol >= 1.0:
        score += 0.2
    score = min(score, 1.0)

    return {
        "rel_volume": round(float(rel_vol), 2),
        "volume_spike": volume_spike,
        "above_vwap": above_vwap,
        "order_book_imbalance": order_book_imbalance,
        "score": round(score, 2),
    }
