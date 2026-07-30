"""
مرحله دهم: News Filter
جلوگیری از سیگنال ۳۰ دقیقه قبل تا ۳۰ دقیقه بعد از اخبار مهم (CPI, FOMC, NFP, ...)
چون هیچ API رایگان و پایداری برای کلندر اقتصادی وجود نداره، رویدادها را خودت (یا ادمین)
با دستور /addnews به ربات اضافه می‌کنید و در جدول news_events ذخیره می‌شود.
"""
import config
import database


def is_blocked_by_news() -> tuple:
    blocked, name = database.is_news_blackout(config.NEWS_BUFFER_MINUTES)
    return blocked, name
