"""
مرحله دوم: Multi Time Frame Analysis
فقط زمانی اجازه سیگنال بده که روند تایم‌های بالاتر هم‌جهت باشند.
"""
import config
import exchange_client
import indicators
from trend_engine import detect_trend


def check_mtf_alignment(exchange_id: str, symbol: str, timeframes_high_to_low: list) -> dict:
    """
    timeframes_high_to_low مثلا: ["1d", "4h", "1h"]
    خروجی: {"aligned": bool, "direction": "bullish"/"bearish"/None, "details": {...}}
    """
    details = {}
    directions = []

    for tf in timeframes_high_to_low:
        df = exchange_client.fetch_ohlcv_df(exchange_id, symbol, tf, limit=250)
        df = indicators.add_all_indicators(df)
        trend_info = detect_trend(df)
        details[tf] = trend_info
        directions.append(trend_info["trend"])

    if all(d == "bullish" for d in directions):
        return {"aligned": True, "direction": "bullish", "details": details}
    if all(d == "bearish" for d in directions):
        return {"aligned": True, "direction": "bearish", "details": details}

    return {"aligned": False, "direction": None, "details": details}
