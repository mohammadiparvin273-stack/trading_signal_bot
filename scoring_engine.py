"""
مرحله هفتم: AI Scoring Engine
به‌جای قانون خشک، به هر شرط امتیاز می‌دهد و در نهایت یک عدد ۰ تا ۱۰۰ تولید می‌کند.
وزن‌ها از config.SCORE_WEIGHTS خوانده می‌شوند (قابل تنظیم توسط learning.py در آینده).
"""
import config
import smart_money


def compute_score(direction: str, last_price: float, trend_info: dict, sweep: dict,
                   obs: list, gaps: list, volume_info: dict, momentum_info: dict) -> dict:
    weights = config.SCORE_WEIGHTS
    reasons = {}
    total = 0.0

    # Trend
    trend_component = trend_info["score"] if trend_info["trend"] == direction else 0
    total += trend_component * weights["trend"]
    reasons["trend"] = bool(trend_component)

    # Liquidity Sweep
    sweep_hit = bool(sweep["detected"] and sweep["direction"] == direction)
    total += (1.0 if sweep_hit else 0) * weights["liquidity_sweep"]
    reasons["liquidity_sweep"] = sweep_hit

    # Order Block
    ob_hit = smart_money.price_in_order_block(last_price, obs, direction)
    total += (1.0 if ob_hit else 0) * weights["order_block"]
    reasons["order_block"] = ob_hit

    # FVG
    fvg_hit = smart_money.price_in_fvg(last_price, gaps, direction)
    total += (1.0 if fvg_hit else 0) * weights["fvg"]
    reasons["fvg"] = fvg_hit

    # VWAP (خرید بالای وی‌واپ، فروش زیر وی‌واپ)
    vwap_hit = False
    if volume_info["above_vwap"] is not None:
        vwap_hit = volume_info["above_vwap"] if direction == "bullish" else not volume_info["above_vwap"]
    total += (1.0 if vwap_hit else 0) * weights["vwap"]
    reasons["vwap"] = vwap_hit

    # Volume
    total += volume_info["score"] * weights["volume"]
    reasons["volume"] = volume_info["score"] >= 0.5

    # Momentum
    total += momentum_info["score"] * weights["momentum"]
    reasons["momentum"] = momentum_info["score"] >= 0.5

    score = round(total, 1)

    if score >= config.MIN_SCORE_STRONG:
        strength = "STRONG"
    elif score >= config.MIN_SCORE_NORMAL:
        strength = "NORMAL"
    else:
        strength = "NONE"

    return {"score": score, "strength": strength, "reasons": reasons}
