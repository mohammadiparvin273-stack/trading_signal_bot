"""
اتصال به Binance و Bybit با ccxt (REST - رایگان و بدون نیاز به کلید برای دیتای عمومی)

نکته‌ی مهم: load_markets() فقط یک‌بار برای هر صرافی انجام می‌شود و کش می‌شود.
اگر شکست بخورد (مثلاً rate limit)، به‌جای تلاش دوباره در همون اجرا (که خودش
باعث تشدید بن شدن می‌شه)، حداقل ۳۰ دقیقه صبر می‌کنیم قبل از تلاش بعدی.
"""
import time
import logging
import ccxt
import pandas as pd
import config

log = logging.getLogger("exchange_client")

_clients = {}
_markets_loaded = set()
_last_load_attempt = {}
LOAD_RETRY_COOLDOWN_SECONDS = 1800  # ۳۰ دقیقه


def get_client(exchange_id: str):
    if exchange_id not in _clients:
        cfg = config.EXCHANGES[exchange_id]
        klass = getattr(ccxt, cfg["id"])
        _clients[exchange_id] = klass({
            "apiKey": cfg["api_key"] or None,
            "secret": cfg["secret"] or None,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                "fetchMarkets": ["spot"],
            },
        })
    return _clients[exchange_id]


def ensure_markets(exchange_id: str) -> bool:
    """بازارهای صرافی رو فقط یک‌بار لود و کش می‌کنه. در صورت شکست، تا ۳۰ دقیقه دیگه تلاش نمی‌کنه."""
    if exchange_id in _markets_loaded:
        return True

    now = time.time()
    last_attempt = _last_load_attempt.get(exchange_id, 0)
    if now - last_attempt < LOAD_RETRY_COOLDOWN_SECONDS:
        return False

    _last_load_attempt[exchange_id] = now
    client = get_client(exchange_id)
    try:
        client.load_markets()
        _markets_loaded.add(exchange_id)
        log.info(f"بازارهای {exchange_id} با موفقیت لود شد.")
        return True
    except Exception as e:
        log.warning(f"لود بازارهای {exchange_id} شکست خورد (تا ۳۰ دقیقه دیگه دوباره تلاش نمی‌کنیم): {e}")
        return False


def fetch_ohlcv_df(exchange_id: str, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    if not ensure_markets(exchange_id):
        raise RuntimeError(f"بازارهای {exchange_id} در دسترس نیست (rate limit/بن موقت).")
    client = get_client(exchange_id)
    raw = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def fetch_order_book_imbalance(exchange_id: str, symbol: str, depth: int = 20) -> float:
    """مثبت یعنی فشار خرید بیشتر، منفی یعنی فشار فروش بیشتر."""
    try:
        if not ensure_markets(exchange_id):
            return 0.0
        client = get_client(exchange_id)
        ob = client.fetch_order_book(symbol, limit=depth)
        bid_vol = sum(b[1] for b in ob["bids"][:depth])
        ask_vol = sum(a[1] for a in ob["asks"][:depth])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return round((bid_vol - ask_vol) / total, 4)
    except Exception:
        return 0.0


def fetch_funding_rate(exchange_id: str, symbol: str):
    try:
        client = get_client(exchange_id)
        fr = client.fetch_funding_rate(symbol)
        return fr.get("fundingRate")
    except Exception:
        return None


def fetch_open_interest(exchange_id: str, symbol: str):
    try:
        client = get_client(exchange_id)
        oi = client.fetch_open_interest(symbol)
        return oi.get("openInterestAmount") or oi.get("openInterestValue")
    except Exception:
        return None
