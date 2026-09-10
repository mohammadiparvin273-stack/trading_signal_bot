"""
Signal Aggregator — combines votes from all strategies (+ optional ML
probability, + optional LLM sentiment) into ONE final signal per asset.

Design goal (per project spec): FEW HIGH-QUALITY SIGNALS.
A trade idea only becomes a signal when there is genuine confluence.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from llm.sentiment import Sentiment
from regime.detector import Regime
from strategies.base import Direction, StrategyVote


@dataclass
class FinalSignal:
    signal_id: str
    timestamp: str
    asset: str
    timeframe: str
    regime: str
    direction: Direction
    entry_low: Optional[float]
    entry_high: Optional[float]
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    risk_reward: Optional[float]
    confidence: float           # 0-100
    strategies: List[str]
    ml_probability: Optional[float]
    llm_sentiment: str
    reason: str
    invalidation: str


MIN_CONFIDENCE = 60.0          # below this -> NEUTRAL / NO SIGNAL
MIN_AGREEING_STRATEGIES = 1    # at least this many non-neutral strategies must agree


def aggregate(asset: str, timeframe: str, regime: Regime, votes: List[StrategyVote],
              ml_probability: Optional[float], llm_sentiment: Sentiment) -> FinalSignal:

    buys = [v for v in votes if v.direction == Direction.BUY]
    sells = [v for v in votes if v.direction == Direction.SELL]

    buy_score = sum(v.strength for v in buys)
    sell_score = sum(v.strength for v in sells)

    if buy_score == 0 and sell_score == 0:
        return _neutral_signal(asset, timeframe, regime, "No strategy found a valid setup on this bar.")

    direction = Direction.BUY if buy_score >= sell_score else Direction.SELL
    agreeing = buys if direction == Direction.BUY else sells
    opposing_score = sell_score if direction == Direction.BUY else buy_score

    if len(agreeing) < MIN_AGREEING_STRATEGIES:
        return _neutral_signal(asset, timeframe, regime, "Not enough strategy confluence for a signal.")

    # Confidence: base from strategy agreement strength, penalized by disagreement,
    # boosted/penalized by ML probability and LLM sentiment when available.
    avg_strength = sum(v.strength for v in agreeing) / len(agreeing)
    agreement_bonus = min(0.25, 0.08 * (len(agreeing) - 1))
    disagreement_penalty = min(0.3, opposing_score * 0.2)

    confidence = avg_strength + agreement_bonus - disagreement_penalty

    if ml_probability is not None:
        # ml_probability is P(up). Align it to the chosen direction.
        directional_prob = ml_probability if direction == Direction.BUY else (1 - ml_probability)
        confidence = 0.65 * confidence + 0.35 * directional_prob
        if directional_prob < 0.5:
            confidence *= 0.8  # ML disagrees -> haircut

    if llm_sentiment != Sentiment.NEUTRAL:
        sentiment_aligned = (
            (direction == Direction.BUY and llm_sentiment == Sentiment.BULLISH) or
            (direction == Direction.SELL and llm_sentiment == Sentiment.BEARISH)
        )
        confidence += 0.05 if sentiment_aligned else -0.08

    confidence_pct = max(0.0, min(1.0, confidence)) * 100

    if confidence_pct < MIN_CONFIDENCE:
        return _neutral_signal(asset, timeframe, regime,
                                f"Confluence found but confidence only {confidence_pct:.0f}% (< {MIN_CONFIDENCE:.0f}% threshold).")

    # Use the strongest agreeing strategy's price levels as the primary levels;
    # this keeps entry/stop/target internally consistent instead of averaging
    # incompatible levels from different strategies.
    primary = max(agreeing, key=lambda v: v.strength)
    entry_low, entry_high = primary.entry_low, primary.entry_high
    stop_loss = primary.stop_loss
    tp1, tp2 = primary.take_profit_1, primary.take_profit_2

    rr = None
    if entry_high and stop_loss and tp1:
        entry_ref = entry_high if direction == Direction.BUY else entry_low
        risk = abs(entry_ref - stop_loss)
        reward = abs(tp1 - entry_ref)
        rr = round(reward / risk, 2) if risk > 0 else None

    reason = " | ".join(f"[{v.strategy_name}] {v.reason}" for v in agreeing)
    invalidation = primary.invalidation or "Primary strategy invalidation level breached."

    return FinalSignal(
        signal_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset=asset,
        timeframe=timeframe,
        regime=regime.value if isinstance(regime, Regime) else str(regime),
        direction=direction,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
        confidence=round(confidence_pct, 1),
        strategies=[v.strategy_name for v in agreeing],
        ml_probability=round(ml_probability * 100, 1) if ml_probability is not None else None,
        llm_sentiment=llm_sentiment.value,
        reason=reason,
        invalidation=invalidation,
    )


def _neutral_signal(asset: str, timeframe: str, regime: Regime, reason: str) -> FinalSignal:
    return FinalSignal(
        signal_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset=asset,
        timeframe=timeframe,
        regime=regime.value if isinstance(regime, Regime) else str(regime),
        direction=Direction.NEUTRAL,
        entry_low=None, entry_high=None, stop_loss=None,
        take_profit_1=None, take_profit_2=None, risk_reward=None,
        confidence=0.0, strategies=[], ml_probability=None,
        llm_sentiment=Sentiment.NEUTRAL.value,
        reason=reason, invalidation="",
    )
