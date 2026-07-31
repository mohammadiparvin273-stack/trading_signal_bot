"""
حلقه‌ی زمان‌بندی: هر SCAN_INTERVAL_MINUTES دقیقه، همه‌ی نمادها روی هر دو صرافی بررسی می‌شوند.
از APScheduler AsyncIO استفاده می‌شود چون خود ربات هم async است (aiohttp + PTB).
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
import pipeline
import telegram_notifier
import outcome_tracker

log = logging.getLogger("scheduler")


async def scan_all():
    for exchange_id in config.EXCHANGES.keys():
        for symbol in config.SYMBOLS:
            try:
                result = await pipeline.analyze_symbol(exchange_id, symbol)
                if result:
                    await telegram_notifier.send_signal(
                        result["signal_id"], result["exchange"], result["symbol"],
                        result["timeframe"], result["direction"], result["score_result"],
                        result["entry"], result["exits"],
                    )
                    log.info(f"سیگنال ارسال شد: {exchange_id} {symbol} {result['direction']}")
            except Exception as e:
                log.exception(f"خطا در تحلیل {exchange_id}/{symbol}: {e}")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        scan_all,
        trigger=IntervalTrigger(minutes=config.SCAN_INTERVAL_MINUTES),
        id="market_scan",
        next_run_time=None,
    )
    scheduler.add_job(
        outcome_tracker.check_open_signals,
        trigger=IntervalTrigger(minutes=10),
        id="outcome_check",
        next_run_time=None,
    )
    scheduler.start()
    return scheduler
