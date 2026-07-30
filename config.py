import os
from dotenv import load_dotenv

load_dotenv()


def _list(env_name: str, default: str):
    raw = os.getenv(env_name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_IDS = set(_list("TELEGRAM_ADMIN_IDS", TELEGRAM_CHAT_ID))

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "10000"))

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Exchanges ---
EXCHANGES = {
    "binance": {
        "api_key": os.getenv("BINANCE_API_KEY", ""),
        "secret": os.getenv("BINANCE_API_SECRET", ""),
        "id": "binance",
    },
    "bybit": {
        "api_key": os.getenv("BYBIT_API_KEY", ""),
        "secret": os.getenv("BYBIT_API_SECRET", ""),
        "id": "bybit",
    },
}

# --- تحلیل ---
SYMBOLS = _list("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT")
TIMEFRAMES = _list("TIMEFRAMES", "1d,4h,1h,15m")
# ترتیب از تایم بالا به پایین باید حفظ شود (برای MTF)
TIMEFRAME_ORDER = ["1M", "1w", "1d", "4h", "1h", "15m", "5m", "1m"]

SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

MIN_SCORE_STRONG = int(os.getenv("MIN_SCORE_STRONG", "85"))
MIN_SCORE_NORMAL = int(os.getenv("MIN_SCORE_NORMAL", "70"))

# --- وزن‌های امتیازدهی (جمعاً 100) ---
SCORE_WEIGHTS = {
    "trend": 20,
    "liquidity_sweep": 15,
    "order_block": 20,
    "fvg": 15,
    "vwap": 10,
    "volume": 10,
    "momentum": 10,
}

# --- ریسک ---
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1"))
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "2"))
MAX_WEEKLY_LOSS_PERCENT = float(os.getenv("MAX_WEEKLY_LOSS_PERCENT", "6"))

# --- فیلتر خبر (دقیقه قبل/بعد) ---
NEWS_BUFFER_MINUTES = 30

TIMEZONE = "Asia/Tehran"
