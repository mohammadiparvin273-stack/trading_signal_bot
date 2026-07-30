"""
پایپ‌لاین کامل طبق معماری: هر نماد/تایم‌فریم/صرافی را از صافی کامل رد می‌کند.
"""
import logging
from psycopg2.extras import Json
import config
import database
import exchange_client
import indicators
import mtf_engine
import smart_money
import volume_engine
import momentum_engine
import regime as regime_module
import scoring_engine
import risk_manager
import news_filter
from trend_engine import detect_trend

log = logging.getLogger("pipeline")

# ترتیب MTF: از تایم بالا به پایین، بر اساس config.TIMEFRAMES (که باید بالا->پایین وارد شده باشه)
MTF_CHAIN = config.TIMEFRAMES  # مثلا ["1d","4h","1h","15m"] - آخری = تایم اجرای سیگنال


async def analyze_symbol(exchange_id: str, symbol: str) -> dict | None:
    # 0) پاز کلی؟
    if database.get_state("paused", "0") == "1":
        return None

    # 0.1) فیلتر ریسک روزانه/هفتگی
    paused, reason = risk_manager.is_trading_paused()
    if paused:
        return None

    # 0.2) فیلتر خبر
    blocked, news_name = news_filter.is_blocked_by_news()
    if blocked:
        log.info(f"سیگنال بلاک شد به خاطر خبر: {news_name}")
        return None

    # 1) MTF Alignment (تایم‌فریم‌های بالاتر از آخرین تایم‌فریم لیست)
    higher_tfs = MTF_CHAIN[:-1]
    exec_tf = MTF_CHAIN[-1]

    if higher_tfs:
        mtf = mtf_engine.check_mtf_alignment(exchange_id, symbol, higher_tfs)
        if not mtf["aligned"]:
            return None
        direction = mtf["direction"]
    else:
        direction = None

    # 2) دیتای تایم اجرا + اندیکاتورها
    df = exchange_client.fetch_ohlcv_df(exchange_id, symbol, exec_tf, limit=300)
    df = indicators.add_all_indicators(df)

    if len(df) < 60:
        return None

    trend_info = detect_trend(df)
    if trend_info["trend"] == "sideways":
        return None  # قانون طلایی: بدون روند، بدون سیگنال

    if direction is None:
        direction = trend_info["trend"]
    elif direction != trend_info["trend"]:
        return None  # تایم اجرا هم‌جهت با تایم‌های بالاتر نیست

    # 3) Market Regime
    regime = regime_module.detect_regime(df)
    if regime not in ("trend",):
        return None  # فقط در رژیم روند معامله می‌کنیم (طبق سند)

    # 4) Smart Money
    sweep = smart_money.detect_liquidity_sweep(df)
    bos_choch = smart_money.detect_bos_choch(df)
    obs = smart_money.detect_order_blocks(df)
    gaps = smart_money.detect_fvg(df)

    # 5) Volume
    ob_imbalance = exchange_client.fetch_order_book_imbalance(exchange_id, symbol)
    volume_info = volume_engine.analyze_volume(df, order_book_imbalance=ob_imbalance)

    # 6) Momentum
    momentum_info = momentum_engine.analyze_momentum(df, direction)

    # 7) Scoring
    last_price = float(df["close"].iloc[-1])
    score_result = scoring_engine.compute_score(
        direction, last_price, trend_info, sweep, obs, gaps, volume_info, momentum_info
    )

    if score_result["strength"] == "NONE":
        return None

    # 8) جلوگیری از سیگنال تکراری پشت‌سرهم روی یک نماد/تایم‌فریم
    last_signal = database.get_last_signal_for(symbol, exec_tf, exchange_id)
    if last_signal and last_signal["direction"] == ("BUY" if direction == "bullish" else "SELL"):
        # اگر آخرین سیگنال هنوز نتیجه‌اش مشخص نشده و همون جهته، دوباره نفرست
        if last_signal["outcome"] is None:
            return None

    # 9) محاسبه سطوح خروج
    atr = float(df["atr"].iloc[-1])
    exits = risk_manager.compute_exit_levels(direction, last_price, atr)

    # 10) ذخیره در دیتابیس
    signal_id = database.save_signal({
        "exchange": exchange_id,
        "symbol": symbol,
        "timeframe": exec_tf,
        "direction": "BUY" if direction == "bullish" else "SELL",
        "score": score_result["score"],
        "strength": score_result["strength"],
        "entry": last_price,
        "stop_loss": exits["stop_loss"],
        "tp1": exits["tp1"],
        "tp2": exits["tp2"],
        "tp3": exits["tp3"],
        "reasons": Json(score_result["reasons"]),
    })

    return {
        "signal_id": signal_id,
        "exchange": exchange_id,
        "symbol": symbol,
        "timeframe": exec_tf,
        "direction": direction,
        "score_result": score_result,
        "entry": last_price,
        "exits": exits,
    }
