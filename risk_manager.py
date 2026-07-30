"""
مرحله هشتم و نهم: مدیریت سرمایه و مدیریت خروج
چون ربات معامله خودکار نمی‌کند، این ماژول فقط:
1) سطوح SL/TP/Trailing پیشنهادی را محاسبه می‌کند (برای نمایش در سیگنال)
2) اگر ضررهای فرضی روزانه/هفتگی (از روی دکمه‌های Win/Loss کاربر) از حد مجاز گذشت، صدور سیگنال جدید را متوقف می‌کند
"""
import config
import database


def compute_exit_levels(direction: str, entry: float, atr: float) -> dict:
    """
    SL: 1.5 * ATR
    TP1: RR=2   (25% خروج)
    TP2: RR=4   (50% خروج)
    TP3/Trailing: باقی‌مانده (25%) با تریلینگ استاپ
    """
    sl_distance = atr * 1.5

    if direction == "bullish":
        stop_loss = entry - sl_distance
        tp1 = entry + sl_distance * 2
        tp2 = entry + sl_distance * 4
        tp3 = entry + sl_distance * 6  # نقطه شروع Trailing
    else:
        stop_loss = entry + sl_distance
        tp1 = entry - sl_distance * 2
        tp2 = entry - sl_distance * 4
        tp3 = entry - sl_distance * 6

    return {
        "stop_loss": round(stop_loss, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "tp3": round(tp3, 6),
        "plan": "25% در TP1 (RR=2) | 50% در TP2 (RR=4) | 25% باقی با Trailing Stop از TP3",
        "risk_per_trade_percent": config.RISK_PER_TRADE_PERCENT,
    }


def is_trading_paused() -> tuple:
    """
    بر اساس تعداد ضررهای ثبت‌شده (از دکمه Loss در تلگرام).
    این یک تخمین ساده‌ست، نه محاسبه دقیق درصد سرمایه (چون معامله واقعی وجود نداره).
    """
    daily_losses = database.get_recent_losses_sum(days=1)
    weekly_losses = database.get_recent_losses_sum(days=7)

    # فرض: هر ضرر ~ RISK_PER_TRADE_PERCENT از سرمایه
    daily_loss_pct = daily_losses * config.RISK_PER_TRADE_PERCENT
    weekly_loss_pct = weekly_losses * config.RISK_PER_TRADE_PERCENT

    if daily_loss_pct >= config.MAX_DAILY_LOSS_PERCENT:
        return True, f"سقف ضرر روزانه ({config.MAX_DAILY_LOSS_PERCENT}%) رد شد. امروز دیگه سیگنال نمی‌فرستم."
    if weekly_loss_pct >= config.MAX_WEEKLY_LOSS_PERCENT:
        return True, f"سقف ضرر هفتگی ({config.MAX_WEEKLY_LOSS_PERCENT}%) رد شد. این هفته دیگه سیگنال نمی‌فرستم."
    return False, None
