"""
Central configuration for the Trading SIGNAL Bot.

IMPORTANT — PROJECT PRINCIPLE:
This bot NEVER places, modifies, or closes orders. It only produces
analysis and signals. Any exchange credentials configured here must be
READ-ONLY (market-data only) — never give it trading or withdrawal
permissions.
"""
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ExchangeConfig:
    # ccxt exchange id — 'binance', 'kraken', 'bybit', etc. Public OHLCV
    # endpoints on these exchanges require NO API key at all.
    #
    # NOTE: Binance blocks requests from many cloud/datacenter IP ranges
    # (including GitHub Actions runners) with an HTTP 451 "restricted
    # location" error. Kraken is used as the default here because it is
    # reliably reachable from GitHub-hosted runners; `fallback_exchange_ids`
    # below are tried automatically, in order, if the primary one fails.
    exchange_id: str = "kraken"
    fallback_exchange_ids: List[str] = field(default_factory=lambda: ["okx", "bybit", "coinbase"])
    api_key: str = os.getenv("EXCHANGE_API_KEY", "")
    api_secret: str = os.getenv("EXCHANGE_API_SECRET", "")
    rate_limit_ms: int = 1200


@dataclass
class RunConfig:
    mode: str = "PAPER_SIGNAL"  # BACKTEST | PAPER_SIGNAL | LIVE_SIGNAL
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframe: str = "1h"  # designed for intraday/swing, not scalping
    poll_seconds: int = 300  # how often to check for new candles in *_SIGNAL modes
    history_bars: int = 1000


@dataclass
class RiskConfig:
    account_equity: float = 1000.0       # used only to compute suggested size, no funds are touched
    max_risk_per_trade_pct: float = 1.0  # % of equity
    min_risk_reward: float = 1.5


@dataclass
class MLConfig:
    enabled: bool = True
    model_type: str = "lightgbm"   # sklearn | xgboost | lightgbm
    min_train_bars: int = 500
    retrain_every_bars: int = 200
    probability_threshold: float = 0.55


@dataclass
class DLConfig:
    # Off by default because it needs `torch` installed (not in the default
    # requirements.txt to keep install light/free-tier friendly). Flip to
    # True and `pip install torch` to use it. Core bot works fully without it.
    enabled: bool = False
    framework: str = "torch"
    min_train_bars: int = 800
    epochs: int = 15


@dataclass
class LLMConfig:
    # ON by default using the free, zero-setup "keyword" backend (no LLM
    # download, no server, no API key — a small open lexicon of bullish/
    # bearish finance words scores free RSS headlines). Upgrade to a real
    # local LLM anytime by switching backend to "ollama" or "local_hf".
    enabled: bool = True
    backend: str = "keyword"  # keyword | ollama | local_hf
    model_path: str = ""
    # Free RSS feeds used as the news source — no API key needed.
    rss_feeds: list = field(default_factory=lambda: [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
    ])
    max_headlines: int = 15


@dataclass
class NotificationConfig:
    console: bool = True
    log_file: str = "signals.log"
    telegram_enabled: bool = os.getenv("TELEGRAM_BOT_TOKEN", "") != ""
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


@dataclass
class Settings:
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    run: RunConfig = field(default_factory=RunConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    dl: DLConfig = field(default_factory=DLConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    signal_store_path: str = "storage/signal_state.json"


SETTINGS = Settings()
