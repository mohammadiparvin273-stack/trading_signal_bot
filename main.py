"""
نقطه ورود پروژه.
حالت Webhook (Render): یک سرور aiohttp خودمون بالا می‌آوریم که هم درخواست‌های
Telegram را جواب می‌دهد و هم یک مسیر ساده‌ی سلامت (health check) دارد تا
سرویس‌های Keep-Alive رایگان (مثل cron-job.org) بتوانند راحت بیدارش نگه دارند.
حالت Polling (اجرای لوکال): از حالت ساده‌ی PTB استفاده می‌کنیم.
"""
import asyncio
import logging
from aiohttp import web
from telegram import Update

import config
import database
import scheduler as scheduler_module
import telegram_notifier

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("main")


async def health(request):
    return web.Response(text="OK - ربات سیگنال‌یاب بیداره")


async def handle_telegram_webhook(request):
    data = await request.json()
    update = Update.de_json(data, telegram_notifier.app.bot)
    await telegram_notifier.app.update_queue.put(update)
    return web.Response(text="OK")


async def start_background_jobs():
    log.info("راه‌اندازی دیتابیس...")
    database.init_db()

    log.info("راه‌اندازی زمان‌بند بازار...")
    sch = scheduler_module.start_scheduler()
    sch.add_job(scheduler_module.scan_all, "date")
    sch.add_job(scheduler_module.outcome_tracker.check_open_signals, "date")

    await telegram_notifier.send_plain("✅ ربات سیگنال‌یاب روشن شد و شروع به رصد بازار کرد.")


async def run_webhook_mode():
    app = telegram_notifier.build_app()
    await app.initialize()
    await app.start()

    await start_background_jobs()

    await app.bot.set_webhook(url=f"{config.WEBHOOK_URL}/webhook", drop_pending_updates=True)

    web_app = web.Application()
    web_app.router.add_get("/", health)
    web_app.router.add_post("/webhook", handle_telegram_webhook)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info(f"سرور روی پورت {config.PORT} بالا اومد (health + webhook)")

    while True:
        await asyncio.sleep(3600)


def run_polling_mode():
    app = telegram_notifier.build_app()

    async def post_init(app):
        await start_background_jobs()

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True)


def main():
    if not config.TELEGRAM_BOT_TOKEN or not config.DATABASE_URL:
        raise RuntimeError("TELEGRAM_BOT_TOKEN و DATABASE_URL باید در .env تنظیم شده باشند.")

    if config.WEBHOOK_URL:
        log.info("اجرا در حالت Webhook (مناسب Render)")
        asyncio.run(run_webhook_mode())
    else:
        log.info("اجرا در حالت Polling (مناسب اجرای لوکال)")
        run_polling_mode()


if __name__ == "__main__":
    main()
