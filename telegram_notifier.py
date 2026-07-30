"""
ارسال سیگنال به تلگرام + دکمه‌های شیشه‌ای Win/Loss برای یادگیری
+ دستورات ادمین: /addnews /stats /pause /resume /news
"""
import jdatetime
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import database
import learning

app: Application = None


def build_app() -> Application:
    global app
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("addnews", cmd_addnews))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CallbackQueryHandler(on_outcome_button))
    return app


def _is_admin(user_id) -> bool:
    return str(user_id) in config.TELEGRAM_ADMIN_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! من ربات سیگنال‌یاب کریپتو هستم 📡\n"
        "روی جفت‌ارزهای " + ", ".join(config.SYMBOLS) + " فعالم.\n\n"
        "دستورات:\n"
        "/stats - آمار عملکرد شرط‌ها\n"
        "/addnews نام | 1404-05-10 14:30 - افزودن خبر مهم (تقویم شمسی، تهران)\n"
        "/news - اخبار پیش‌رو\n"
        "/pause - توقف موقت سیگنال‌ها\n"
        "/resume - از سرگیری سیگنال‌ها"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = database.get_condition_stats()
    if not stats:
        await update.message.reply_text("هنوز آماری ثبت نشده.")
        return
    lines = ["📊 آمار عملکرد شرط‌ها:\n"]
    for s in stats:
        total = s["wins"] + s["losses"]
        wr = (s["wins"] / total * 100) if total else 0
        lines.append(f"• {s['condition_name']}: {s['wins']}برد/{s['losses']}باخت ({wr:.0f}%)")
    await update.message.reply_text("\n".join(lines))


async def cmd_addnews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین می‌تونه خبر اضافه کنه.")
        return
    try:
        text = update.message.text.split(" ", 1)[1]
        name, jdate_str = [p.strip() for p in text.split("|")]
        j_date, j_time = jdate_str.split(" ")
        y, m, d = map(int, j_date.split("-"))
        hh, mm = map(int, j_time.split(":"))
        g_dt = jdatetime.datetime(y, m, d, hh, mm).togregorian()
        g_dt = g_dt.replace(tzinfo=timezone.utc)  # ساده‌سازی: فرض بر ورودی UTC یا تنظیم دستی آفست
        database.add_news_event(name, g_dt)
        await update.message.reply_text(f"✅ خبر «{name}» اضافه شد.")
    except Exception as e:
        await update.message.reply_text(
            "فرمت درست: /addnews CPI | 1404-05-10 14:30\n"
            f"خطا: {e}"
        )


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = database.get_upcoming_news(hours=72)
    if not events:
        await update.message.reply_text("خبر مهمی برای ۷۲ ساعت آینده ثبت نشده.")
        return
    lines = ["📅 اخبار پیش‌رو:\n"]
    for e in events:
        jt = jdatetime.datetime.fromgregorian(datetime=e["event_time"])
        lines.append(f"• {e['name']} - {jt.strftime('%Y/%m/%d %H:%M')}")
    await update.message.reply_text("\n".join(lines))


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    database.set_state("paused", "1")
    await update.message.reply_text("⏸ سیگنال‌ها متوقف شدند.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    database.set_state("paused", "0")
    await update.message.reply_text("▶️ سیگنال‌ها از سر گرفته شدند.")


async def on_outcome_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, signal_id = query.data.split(":")
    signal_id = int(signal_id)

    if action == "win":
        learning.record_outcome(signal_id, win=True)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ ثبت شد: برد")
    elif action == "loss":
        learning.record_outcome(signal_id, win=False)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("❌ ثبت شد: ضرر")


def format_signal_message(exchange_id: str, symbol: str, timeframe: str, direction: str,
                           score_result: dict, entry: float, exits: dict) -> str:
    emoji = "🟢" if direction == "bullish" else "🔴"
    side = "BUY (لانگ)" if direction == "bullish" else "SELL (شورت)"
    now_j = jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M")

    active_reasons = [k for k, v in score_result["reasons"].items() if v]
    reasons_fa = {
        "trend": "روند همسو",
        "liquidity_sweep": "جمع‌آوری نقدینگی",
        "order_block": "Order Block",
        "fvg": "Fair Value Gap",
        "vwap": "موقعیت نسبت به VWAP",
        "volume": "حجم معتبر",
        "momentum": "مومنتوم قوی",
    }
    reasons_txt = "، ".join(reasons_fa.get(r, r) for r in active_reasons) or "-"

    strength_fa = {"STRONG": "💪 قوی", "NORMAL": "معمولی"}.get(score_result["strength"], "")

    return (
        f"{emoji} سیگنال {side} - {strength_fa}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"صرافی: {exchange_id.capitalize()}\n"
        f"نماد: {symbol}\n"
        f"تایم‌فریم: {timeframe}\n"
        f"امتیاز: {score_result['score']}/100\n"
        f"دلایل: {reasons_txt}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ورود: {entry}\n"
        f"حد ضرر: {exits['stop_loss']}\n"
        f"TP1: {exits['tp1']}   TP2: {exits['tp2']}   TP3: {exits['tp3']}\n"
        f"پلن خروج: {exits['plan']}\n"
        f"ریسک پیشنهادی: {exits['risk_per_trade_percent']}٪ سرمایه\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕐 {now_j} (تهران)\n"
        f"⚠️ این سیگنال صرفاً جهت اطلاع است، توصیه مالی نیست."
    )


async def send_signal(signal_id: int, exchange_id: str, symbol: str, timeframe: str,
                       direction: str, score_result: dict, entry: float, exits: dict):
    text = format_signal_message(exchange_id, symbol, timeframe, direction, score_result, entry, exits)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ برد", callback_data=f"win:{signal_id}"),
        InlineKeyboardButton("❌ ضرر", callback_data=f"loss:{signal_id}"),
    ]])
    msg = await app.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard
    )
    database.set_telegram_message_id(signal_id, msg.message_id)


async def send_plain(text: str):
    await app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
