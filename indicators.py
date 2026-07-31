"""
اندیکاتورهای پایه با کتابخونه‌ی "ta" (پایدار، خالص پایتون)
"""
import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["ema50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["ema200"] = EMAIndicator(close=df["close"], window=200).ema_indicator()
    df["ema20"] = EMAIndicator(close=df["close"], window=20).ema_indicator()

    adx_ind = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14)
    df["adx"] = adx_ind.adx()

    df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()

    macd_ind = MACD(close=df["close"])
    df["macd_hist"] = macd_ind.macd_diff()

    atr_ind = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
    df["atr"] = atr_ind.average_true_range()
    df["atr_sma"] = df["atr"].rolling(20).mean()

    df["vol_sma20"] = df["volume"].rolling(20).mean()
    df["rel_volume"] = df["volume"] / df["vol_sma20"]

    # VWAP (روزانه ساده - از شروع دیتافریم)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

    return df
