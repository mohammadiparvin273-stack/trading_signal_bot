"""
اندیکاتورهای پایه با pandas_ta (خالص پایتون، نیازی به کامپایل TA-Lib نیست)
"""
import pandas as pd
import pandas_ta as ta


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)
    df["ema20"] = ta.ema(df["close"], length=20)

    adx = ta.adx(df["high"], df["low"], df["close"], length=14)
    if adx is not None:
        df["adx"] = adx["ADX_14"]

    df["rsi"] = ta.rsi(df["close"], length=14)

    macd = ta.macd(df["close"])
    if macd is not None:
        df["macd_hist"] = macd["MACDh_12_26_9"]

    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr_sma"] = df["atr"].rolling(20).mean()

    df["vol_sma20"] = df["volume"].rolling(20).mean()
    df["rel_volume"] = df["volume"] / df["vol_sma20"]

    # VWAP (روزانه ساده - از شروع دیتافریم)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

    return df
