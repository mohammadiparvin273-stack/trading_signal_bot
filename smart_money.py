"""
مرحله سوم: Smart Money Concepts
تشخیص: Liquidity Sweep, BOS, CHOCH, Order Block, Fair Value Gap
"""
import pandas as pd
from trend_engine import detect_swing_structure


def detect_liquidity_sweep(df: pd.DataFrame, window: int = 20) -> dict:
    """
    قیمت با فتیله از یک سقف/کف اخیر رد می‌شود ولی با بدنه‌ی کندل داخل رنج قبلی بسته می‌شود
    (شکار استاپ / جمع‌آوری نقدینگی)
    """
    recent = df.iloc[-window:-1]
    last = df.iloc[-1]

    recent_high = recent["high"].max()
    recent_low = recent["low"].min()

    bullish_sweep = last["low"] < recent_low and last["close"] > recent_low
    bearish_sweep = last["high"] > recent_high and last["close"] < recent_high

    if bullish_sweep:
        return {"detected": True, "direction": "bullish", "level": float(recent_low)}
    if bearish_sweep:
        return {"detected": True, "direction": "bearish", "level": float(recent_high)}
    return {"detected": False, "direction": None, "level": None}


def detect_bos_choch(df: pd.DataFrame, window: int = 5) -> dict:
    """
    BOS: ادامه‌ی روند با شکست ساختار هم‌جهت
    CHOCH: تغییر جهت ساختار (اولین شکست خلاف روند قبلی)
    """
    structure, pivot_highs, pivot_lows = detect_swing_structure(df, window=window)
    last_close = df["close"].iloc[-1]

    event = {"bos": None, "choch": None}

    if len(pivot_highs) >= 1:
        last_high_idx, last_high_val = pivot_highs[-1]
        if last_close > last_high_val:
            event["bos"] = "bullish" if structure == "bullish" else None
            event["choch"] = "bullish" if structure != "bullish" else None

    if len(pivot_lows) >= 1:
        last_low_idx, last_low_val = pivot_lows[-1]
        if last_close < last_low_val:
            event["bos"] = "bearish" if structure == "bearish" else event["bos"]
            event["choch"] = "bearish" if structure != "bearish" else event["choch"]

    return event


def detect_order_blocks(df: pd.DataFrame, lookback: int = 30) -> list:
    """
    Order Block ساده:
    - Bullish OB: آخرین کندل نزولی قبل از یک حرکت صعودی قوی که ساختار را می‌شکند
    - Bearish OB: آخرین کندل صعودی قبل از یک حرکت نزولی قوی که ساختار را می‌شکند
    """
    obs = []
    sub = df.iloc[-lookback:].reset_index(drop=True)

    for i in range(1, len(sub) - 1):
        candle = sub.iloc[i]
        next_candle = sub.iloc[i + 1]
        body = abs(candle["close"] - candle["open"])
        next_body = abs(next_candle["close"] - next_candle["open"])
        is_bearish_candle = candle["close"] < candle["open"]
        is_bullish_candle = candle["close"] > candle["open"]
        strong_move = next_body > body * 1.5

        if is_bearish_candle and next_candle["close"] > candle["high"] and strong_move:
            obs.append({
                "type": "bullish",
                "top": float(candle["high"]),
                "bottom": float(candle["low"]),
            })
        if is_bullish_candle and next_candle["close"] < candle["low"] and strong_move:
            obs.append({
                "type": "bearish",
                "top": float(candle["high"]),
                "bottom": float(candle["low"]),
            })

    return obs[-3:]  # فقط ۳ تای آخر برای کارایی


def price_in_order_block(price: float, obs: list, direction: str) -> bool:
    for ob in obs:
        if ob["type"] == direction and ob["bottom"] <= price <= ob["top"]:
            return True
    return False


def detect_fvg(df: pd.DataFrame, lookback: int = 30) -> list:
    """
    Fair Value Gap با روش سه‌کندلی:
    - Bullish FVG: high کندل ۱ < low کندل ۳
    - Bearish FVG: low کندل ۱ > high کندل ۳
    """
    gaps = []
    sub = df.iloc[-lookback:].reset_index(drop=True)

    for i in range(len(sub) - 2):
        c1, c3 = sub.iloc[i], sub.iloc[i + 2]
        if c1["high"] < c3["low"]:
            gaps.append({"type": "bullish", "top": float(c3["low"]), "bottom": float(c1["high"])})
        if c1["low"] > c3["high"]:
            gaps.append({"type": "bearish", "top": float(c1["low"]), "bottom": float(c3["high"])})

    return gaps[-3:]


def price_in_fvg(price: float, gaps: list, direction: str) -> bool:
    for g in gaps:
        if g["type"] == direction and g["bottom"] <= price <= g["top"]:
            return True
    return False
