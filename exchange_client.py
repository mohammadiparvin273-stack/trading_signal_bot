"""
اتصال به Binance و Bybit با ccxt (REST - رایگان و بدون نیاز به کلید برای دیتای عمومی)
"""
import ccxt
import pandas as pd
import config

_clients = {}


def get_client(exchange_id: str):
    if exchange_id not in _clients:
        cfg = config.EXCHANGES[exchange_id]
        klass = getattr(ccxt, cfg["id"])
        _clients[exchange_id] = klass({
            "apiKey": cfg["api_key"] or None,
            "secret": cfg["secret"] or None,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}, # دیتای فیوچرز برای OI/Funding
        })
    return _clients[exchange_id]


def fetch_ohlcv_df(exchange_id: str, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    client = get_client(exchange_id)
    raw = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def fetch_order_book_imbalance(exchange_id: str, symbol: str, depth: int = 20) -> float:
    """مثبت یعنی فشار خرید بیشتر، منفی یعنی فشار فروش بیشتر."""
    try:
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
