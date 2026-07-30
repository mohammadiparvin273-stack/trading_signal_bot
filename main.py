"""
نقطه ورود پروژه.
روی Render به‌صورت Web Service اجرا می‌شود (webhook تلگرام + health check روی همون پورت).
"""
import logging
from telegram.ext import ContextTypes

import config
import database
import scheduler as scheduler_module
import telegram_notifier

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("main")


async def post_init(app):
    log.info("راه‌اندازی دیتابیس...")
    database.init_db()

    log.info("راه‌اندازی زمان‌بند بازار...")
    sch = scheduler_module.start_scheduler()
    app.bot_data["scheduler"] = sch

    # اولین اسکن با کمی تاخیر بعد از بالا آمدن کامل
    sch.add_job(scheduler_module.scan_all, "date")

    await telegram_notifier.send_plain("✅ ربات سیگنال‌یاب روشن شد و شروع به رصد بازار کرد.")


def main():
    if not config.TELEGRAM_BOT_TOKEN or not config.DATABASE_URL:
        raise RuntimeError("TELEGRAM_BOT_TOKEN و DATABASE_URL باید در .env تنظیم شده باشند.")

    app = telegram_notifier.build_app()
    app.post_init = post_init

    if config.WEBHOOK_URL:
        log.info("اجرا در حالت Webhook (مناسب Render)")
        app.run_webhook(
            listen="0.0.0.0",
            port=config.PORT,
            url_path="webhook",
            webhook_url=f"{config.WEBHOOK_URL}/webhook",
            drop_pending_updates=True,
        )
    else:
        log.info("اجرا در حالت Polling (مناسب اجرای لوکال)")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
