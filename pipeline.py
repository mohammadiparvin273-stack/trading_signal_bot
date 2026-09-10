"""
The core pipeline, matching the required architecture exactly:

Market Data -> Data Validation -> Feature Engineering -> Regime Detection
-> Strategy Engine -> ML Model -> Optional LLM Sentiment
-> Signal Aggregator -> Risk Analysis -> Signal Generator -> Notification

No step here ever places, modifies, or cancels an order.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from aggregator.formatter import format_signal_message
from aggregator.signal_aggregator import FinalSignal, aggregate
from config.settings import SETTINGS
from data.fetcher import MarketDataFetcher
from data.validation import validate_ohlcv
from dl.model import SignalDLModel
from features.engineering import build_features
from llm.news_fetcher import fetch_headlines
from llm.sentiment import Sentiment, get_sentiment
from ml.model import SignalMLModel
from regime.detector import detect_regime
from risk.risk_analysis import assess_risk
from storage import history_store, run_log
from storage.signal_store import SignalStore
from strategies.base import Direction
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy

STRATEGIES = [
    TrendFollowingStrategy(),
    MomentumStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
]


class SignalPipeline:
    def __init__(self):
        self.fetcher = MarketDataFetcher()
        self.store = SignalStore()
        self._ml_models: dict[str, SignalMLModel] = {}
        self._dl_models: dict[str, SignalDLModel] = {}

    def _get_ml_model(self, asset: str, features_df: pd.DataFrame) -> Optional[SignalMLModel]:
        if not SETTINGS.ml.enabled:
            return None
        model = self._ml_models.get(asset)
        if model is None or len(features_df) % SETTINGS.ml.retrain_every_bars == 0:
            model = SignalMLModel()
            model.fit(features_df)
            self._ml_models[asset] = model
        return model

    def _get_dl_model(self, asset: str, features_df: pd.DataFrame) -> Optional[SignalDLModel]:
        if not SETTINGS.dl.enabled:
            return None
        model = self._dl_models.get(asset)
        if model is None or len(features_df) % SETTINGS.ml.retrain_every_bars == 0:
            model = SignalDLModel()
            model.fit(features_df)
            self._dl_models[asset] = model
        return model

    def process_symbol(self, asset: str, timeframe: Optional[str] = None,
                        df_override: Optional[pd.DataFrame] = None) -> FinalSignal:
        timeframe = timeframe or SETTINGS.run.timeframe

        # 1. Market Data — fetch fresh candles, then merge into the
        # PERSISTED history file (storage/history/*.csv). This is the
        # dataset the ML/DL models actually train on: it accumulates
        # real market data across every run instead of starting from
        # zero each time.
        if df_override is not None:
            clean = validate_ohlcv(df_override)
        else:
            fresh = self.fetcher.fetch_ohlcv(asset, timeframe=timeframe, limit=SETTINGS.run.history_bars)
            merged = history_store.save_and_merge(asset, timeframe, fresh)
            # 2. Data Validation
            clean = validate_ohlcv(merged)
        # 3. Feature Engineering
        feats = build_features(clean)
        # 4. Market Regime Detection
        regime = detect_regime(feats.iloc[-1])
        # 5-8. Strategy Engine (Trend/Momentum/Breakout/Mean-Reversion)
        votes = [s.evaluate(feats) for s in STRATEGIES]
        # 10. ML Model (optional)
        ml_model = self._get_ml_model(asset, feats)
        ml_prob = ml_model.predict_proba_up(feats) if ml_model else None
        # Optional Deep Learning model — if both ML and DL are enabled,
        # average their probability-of-up estimates; if only one is
        # enabled/available, use that one; if neither, ml_prob stays None.
        dl_model = self._get_dl_model(asset, feats)
        dl_prob = dl_model.predict_proba_up(feats) if dl_model else None
        if ml_prob is not None and dl_prob is not None:
            ml_prob = (ml_prob + dl_prob) / 2
        elif dl_prob is not None:
            ml_prob = dl_prob
        # Optional Sentiment layer: free RSS headlines -> keyword/LLM sentiment.
        # Safe by construction: any failure here (offline, feed down, no LLM
        # configured) yields Neutral and never breaks the pipeline.
        headlines = fetch_headlines() if SETTINGS.llm.enabled else None
        sentiment = get_sentiment(headlines)
        # 11. Signal Aggregator
        signal = aggregate(asset, timeframe, regime, votes, ml_prob, sentiment)
        # 12. Risk Analysis (informational only)
        if signal.direction != Direction.NEUTRAL:
            entry_ref = signal.entry_high if signal.direction == Direction.BUY else signal.entry_low
            risk = assess_risk(signal.direction, entry_ref, signal.stop_loss,
                                signal.take_profit_1, feats.iloc[-1]["atr_pct"])
        else:
            risk = None

        self._last_risk = risk
        return signal

    def process_and_notify(self, asset: str, timeframe: Optional[str] = None) -> Optional[FinalSignal]:
        """Full PAPER_SIGNAL / LIVE_SIGNAL step: generate signal, dedupe, notify, log."""
        from notification.notifiers import notify_all

        signal = self.process_symbol(asset, timeframe)
        should_send, change_type = self.store.should_notify(signal)
        if should_send:
            message = format_signal_message(signal, getattr(self, "_last_risk", None))
            if change_type != "NEW_SIGNAL":
                message = f"[{change_type}]\n" + message
            notify_all(message)
            self.store.record(signal)

        # Log EVERY result (including NEUTRAL / not-notified) so the
        # dashboard can show the full picture, not just what got sent.
        run_log.append_run({
            "asset": signal.asset,
            "timeframe": signal.timeframe,
            "regime": signal.regime,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "ml_probability": signal.ml_probability,
            "llm_sentiment": signal.llm_sentiment,
            "entry_low": signal.entry_low,
            "entry_high": signal.entry_high,
            "stop_loss": signal.stop_loss,
            "take_profit_1": signal.take_profit_1,
            "risk_reward": signal.risk_reward,
            "strategies": signal.strategies,
            "reason": signal.reason,
            "notified": should_send,
            "change_type": change_type,
            "signal_id": signal.signal_id,
        })

        return signal if should_send else None
