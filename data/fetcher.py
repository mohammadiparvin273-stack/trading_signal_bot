"""
Free, read-only market data fetcher.

Uses ccxt's PUBLIC endpoints only (fetch_ohlcv). No API key is required
for this. If the user supplies an API key in settings, it is only ever
used with ccxt in a way that CANNOT place orders — this module never
calls create_order / cancel_order / withdraw / transfer, and never will.
"""
from __future__ import annotations

import time
from typing import Optional

import ccxt
import pandas as pd

from config.settings import SETTINGS


class MarketDataFetcher:
    def __init__(self, exchange_id: Optional[str] = None):
        self._preferred_id = exchange_id or SETTINGS.exchange.exchange_id
        candidate_ids = [self._preferred_id] + [
            e for e in SETTINGS.exchange.fallback_exchange_ids if e != self._preferred_id
        ]
        self.exchange = None
        self.exchange_id = None
        last_error = None

        for candidate in candidate_ids:
            try:
                exchange_cls = getattr(ccxt, candidate)
                exchange = exchange_cls(
                    {
                        # Even if keys are present, this class is READ-ONLY by
                        # design: only fetch_ohlcv / fetch_ticker are ever called.
                        "apiKey": SETTINGS.exchange.api_key or None,
                        "secret": SETTINGS.exchange.api_secret or None,
                        "enableRateLimit": True,
                        "rateLimit": SETTINGS.exchange.rate_limit_ms,
                    }
                )
                exchange.load_markets()  # cheap sanity check that this exchange is actually reachable
                self.exchange = exchange
                self.exchange_id = candidate
                if candidate != self._preferred_id:
                    print(f"[warn] '{self._preferred_id}' unreachable — using fallback exchange '{candidate}' instead.")
                break
            except Exception as e:
                last_error = e
                continue

        if self.exchange is None:
            raise ConnectionError(
                f"Could not reach any configured exchange ({candidate_ids}). "
                f"Last error: {last_error}. This can happen if an exchange blocks "
                f"the runner's IP (e.g. Binance returns HTTP 451 for many cloud "
                f"datacenter IPs, including GitHub Actions) — try adding another "
                f"exchange id to fallback_exchange_ids in config/settings.py."
            )

    def _symbol_for_exchange(self, symbol: str) -> str:
        """Map a unified symbol like 'BTC/USDT' to whatever this exchange
        actually lists it as (mainly relevant for Coinbase-style venues)."""
        if symbol in self.exchange.markets:
            return symbol
        # Coinbase (and a few others) often use USD instead of USDT.
        if symbol.endswith("/USDT") and symbol.replace("/USDT", "/USD") in self.exchange.markets:
            return symbol.replace("/USDT", "/USD")
        return symbol

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500,
                     since: Optional[int] = None) -> pd.DataFrame:
        """Fetch OHLCV candles as a clean, sorted, de-duplicated DataFrame."""
        sym = self._symbol_for_exchange(symbol)
        raw = self.exchange.fetch_ohlcv(sym, timeframe=timeframe, since=since, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_ohlcv_history(self, symbol: str, timeframe: str, total_bars: int) -> pd.DataFrame:
        """Page backward through free public history until `total_bars` are collected."""
        sym = self._symbol_for_exchange(symbol)
        limit_per_call = 1000
        all_frames = []
        since = None
        collected = 0
        # Walk backwards: fetch latest, then keep requesting earlier pages.
        ms_per_bar = self.exchange.parse_timeframe(timeframe) * 1000
        end_time = self.exchange.milliseconds()
        while collected < total_bars:
            fetch_since = end_time - ms_per_bar * min(limit_per_call, total_bars - collected + limit_per_call)
            batch = self.exchange.fetch_ohlcv(sym, timeframe=timeframe, since=fetch_since, limit=limit_per_call)
            if not batch:
                break
            df = pd.DataFrame(batch, columns=["timestamp", "open", "high", "low", "close", "volume"])
            all_frames.append(df)
            collected = sum(len(f) for f in all_frames)
            new_end = df["timestamp"].min() - ms_per_bar
            if new_end >= end_time:
                break
            end_time = new_end
            time.sleep(self.exchange.rateLimit / 1000)
            if len(batch) < limit_per_call:
                break
        if not all_frames:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        full = pd.concat(all_frames, ignore_index=True)
        full["timestamp"] = pd.to_datetime(full["timestamp"], unit="ms", utc=True)
        full = full.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
        return full.tail(total_bars).reset_index(drop=True)
