"""
مرحله یازدهم: AI Learning (نسخه ساده - قابل ارتقا به XGBoost وقتی داده کافی جمع شد)
هر بار کاربر روی دکمه Win/Loss می‌زند، برای هر شرطی که در آن سیگنال فعال بوده
آمار برد/باخت آپدیت می‌شود. بعداً می‌شود از این آمار برای تنظیم وزن‌های
config.SCORE_WEIGHTS استفاده کرد (دستی یا خودکار).
"""
import database


def record_outcome(signal_id: int, win: bool):
    signal = database.get_signal(signal_id)
    if not signal:
        return

    database.set_outcome(signal_id, "WIN" if win else "LOSS")

    reasons = signal.get("reasons") or {}
    for condition_name, was_active in reasons.items():
        if was_active:
            database.bump_condition_stat(condition_name, win=win)


def suggest_weight_adjustments() -> dict:
    """
    پیشنهاد ساده: شرط‌هایی که وین‌ریت بالاتر از میانگین دارند وزن بیشتر بگیرند.
    این فقط یک پیشنهاد است؛ اعمال آن روی config دستی انجام می‌شود تا از تغییرات ناگهانی جلوگیری شود.
    """
    stats = database.get_condition_stats()
    suggestions = {}
    for s in stats:
        total = s["wins"] + s["losses"]
        if total < 10:
            continue  # داده کافی نیست
        win_rate = s["wins"] / total
        suggestions[s["condition_name"]] = {
            "win_rate": round(win_rate, 2),
            "sample_size": total,
            "suggestion": "افزایش وزن" if win_rate > 0.55 else ("کاهش وزن" if win_rate < 0.45 else "بدون تغییر"),
        }
    return suggestions
