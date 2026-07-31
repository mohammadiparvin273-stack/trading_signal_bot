"""
پیگیری خودکار نتیجه‌ی سیگنال‌های باز:
هر چند دقیقه یک‌بار، برای سیگنال‌هایی که هنوز نتیجه‌شون مشخص نیست،
کندل‌های بعد از لحظه‌ی صدور سیگنال را می‌خواند و می‌بیند اول به
حد ضرر خورده یا به TP1 - و خودش WIN/LOSS را ثبت و به کاربر اطلاع می‌دهد.
"""
import logging
import config
import database
import exchange_client
import learning
import telegram_notifier

log = logging.getLogger("outcome_tracker")

CHECK_TIMEFRAME = config.TIMEFRAMES[-1]  # همون تایم‌فریمی که سیگنال‌ها روش صادر می‌شن


async def check_open_signals():
    open_signals = database.get_open_signals()
    for sig in open_signals:
        try:
            await _check_one(sig)
        except Exception as e:
            log.exception(f"خطا در بررسی نتیجه سیگنال #{sig['id']}: {e}")


async def _check_one(sig):
    df = exchange_client.fetch_ohlcv_df(sig["exchange"], sig["symbol"], CHECK_TIMEFRAME, limit=500)

    created_at = sig["created_at"]
    df = df[df["timestamp"] >= created_at]
    if df.empty:
        return

    direction = sig["direction"]
    sl = float(sig["stop_loss"])
    tp1 = float(sig["tp1"])

    outcome = None
    for _, candle in df.iterrows():
        high, low = float(candle["high"]), float(candle["low"])
        if direction == "BUY":
            hit_sl = low <= sl
            hit_tp = high >= tp1
        else:
            hit_sl = high >= sl
            hit_tp = low <= tp1

        if hit_sl:
            outcome = "LOSS"
            break
        if hit_tp:
            outcome = "WIN"
            break

    if not outcome:
        return

    learning.record_outcome(sig["id"], win=(outcome == "WIN"))
    await _notify(sig, outcome)


async def _notify(sig, outcome: str):
    if sig.get("telegram_message_id"):
        try:
            await telegram_notifier.app.bot.edit_message_reply_markup(
                chat_id=config.TELEGRAM_CHAT_ID,
                message_id=sig["telegram_message_id"],
                reply_markup=None,
            )
        except Exception:
            pass

    emoji = "✅" if outcome == "WIN" else "❌"
    label = "برد" if outcome == "WIN" else "ضرر"
    await telegram_notifier.send_plain(
        f"{emoji} نتیجه‌ی خودکار سیگنال #{sig['id']} ({sig['symbol']} - {sig['timeframe']}): {label}\n"
        f"(این تشخیص خودکاره؛ اگه با واقعیت معامله‌ی خودت فرق داشت، مهم نیست، فقط برای آمار داخلی رباته)"
    )
