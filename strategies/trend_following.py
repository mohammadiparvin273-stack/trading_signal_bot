from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Direction, StrategyVote


class TrendFollowingStrategy(BaseStrategy):
    """EMA stack + ADX trend strength: ride the trend, pull back to EMA21 for entry."""
    name = "Trend Following"

    def evaluate(self, df: pd.DataFrame) -> StrategyVote:
        row = df.iloc[-1]
        close, ema9, ema21, ema50, ema200 = (
            row["close"], row["ema_9"], row["ema_21"], row["ema_50"], row["ema_200"]
        )
        adx = row["adx_14"]
        atr = row["atr_14"]

        bull_stack = ema9 > ema21 > ema50 > ema200
        bear_stack = ema9 < ema21 < ema50 < ema200
        strong = adx >= 20

        if bull_stack and strong and close > ema21:
            strength = min(1.0, (adx - 20) / 30 + 0.4)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.BUY,
                strength=strength,
                entry_low=round(ema21, 6),
                entry_high=round(close, 6),
                stop_loss=round(min(ema50, close - 1.5 * atr), 6),
                take_profit_1=round(close + 1.5 * atr, 6),
                take_profit_2=round(close + 3.0 * atr, 6),
                reason="EMA stack aligned bullish (9>21>50>200) with ADX confirming trend strength; price holding above EMA21.",
                invalidation=f"Daily/period close back below EMA50 ({ema50:.6f}) or ADX dropping under 18.",
            )
        if bear_stack and strong and close < ema21:
            strength = min(1.0, (adx - 20) / 30 + 0.4)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.SELL,
                strength=strength,
                entry_low=round(close, 6),
                entry_high=round(ema21, 6),
                stop_loss=round(max(ema50, close + 1.5 * atr), 6),
                take_profit_1=round(close - 1.5 * atr, 6),
                take_profit_2=round(close - 3.0 * atr, 6),
                reason="EMA stack aligned bearish (9<21<50<200) with ADX confirming trend strength; price holding below EMA21.",
                invalidation=f"Close back above EMA50 ({ema50:.6f}) or ADX dropping under 18.",
            )
        return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="No clean EMA stack / insufficient trend strength.")
