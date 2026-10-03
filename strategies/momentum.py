from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Direction, StrategyVote


class MomentumStrategy(BaseStrategy):
    """RSI + MACD histogram momentum confirmation.

    FIX (based on ~3 weeks of live results): the original stop/target
    multipliers gave a Risk:Reward of 1.5/2.0 = 0.75 — WORSE than 1:1.
    With R:R below 1, the strategy needs a win rate above 57% just to
    break even (win_rate > risk/(risk+reward)); live win rate was only
    34.8%, so it was structurally guaranteed to lose money regardless of
    signal quality. New multipliers: stop 1.5x ATR (tighter), TP1 2.25x
    ATR, TP2 3.5x ATR -> R:R = 1.5, needing only >40% win rate to break
    even. RSI bounds also tightened (was 25-50 / 50-75, now 25-42 / 58-75)
    so the strategy requires more conviction before firing instead of
    reacting to minor pullbacks inside a larger trend.
    """
    name = "Momentum"

    def evaluate(self, df: pd.DataFrame) -> StrategyVote:
        row = df.iloc[-1]
        prev = df.iloc[-2]
        close, rsi, atr = row["close"], row["rsi_14"], row["atr_14"]
        macd_hist, macd_hist_prev = row["macd_hist"], prev["macd_hist"]

        macd_rising = macd_hist > macd_hist_prev
        macd_falling = macd_hist < macd_hist_prev

        if 58 < rsi < 75 and macd_hist > 0 and macd_rising:
            strength = min(1.0, (rsi - 58) / 17 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.BUY,
                strength=strength,
                entry_low=round(close - 0.3 * atr, 6),
                entry_high=round(close, 6),
                stop_loss=round(close - 1.5 * atr, 6),
                take_profit_1=round(close + 2.25 * atr, 6),
                take_profit_2=round(close + 3.5 * atr, 6),
                reason=f"RSI at {rsi:.1f} (strong bullish zone) with rising positive MACD histogram — momentum building.",
                invalidation="MACD histogram turns negative or RSI drops below 55.",
            )
        if 25 < rsi < 42 and macd_hist < 0 and macd_falling:
            strength = min(1.0, (42 - rsi) / 17 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.SELL,
                strength=strength,
                entry_low=round(close, 6),
                entry_high=round(close + 0.3 * atr, 6),
                stop_loss=round(close + 1.5 * atr, 6),
                take_profit_1=round(close - 2.25 * atr, 6),
                take_profit_2=round(close - 3.5 * atr, 6),
                reason=f"RSI at {rsi:.1f} (strong bearish zone) with falling negative MACD histogram — downside momentum building.",
                invalidation="MACD histogram turns positive or RSI rises above 45.",
            )
        return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="RSI/MACD not aligned for a momentum entry.")
