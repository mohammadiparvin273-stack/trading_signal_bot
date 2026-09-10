from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Direction, StrategyVote


class MomentumStrategy(BaseStrategy):
    """RSI + MACD histogram momentum confirmation."""
    name = "Momentum"

    def evaluate(self, df: pd.DataFrame) -> StrategyVote:
        row = df.iloc[-1]
        prev = df.iloc[-2]
        close, rsi, atr = row["close"], row["rsi_14"], row["atr_14"]
        macd_hist, macd_hist_prev = row["macd_hist"], prev["macd_hist"]

        macd_rising = macd_hist > macd_hist_prev
        macd_falling = macd_hist < macd_hist_prev

        if 50 < rsi < 75 and macd_hist > 0 and macd_rising:
            strength = min(1.0, (rsi - 50) / 25 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.BUY,
                strength=strength,
                entry_low=round(close - 0.3 * atr, 6),
                entry_high=round(close, 6),
                stop_loss=round(close - 2.0 * atr, 6),
                take_profit_1=round(close + 1.5 * atr, 6),
                take_profit_2=round(close + 3.0 * atr, 6),
                reason=f"RSI at {rsi:.1f} (bullish zone, not overbought) with rising positive MACD histogram — momentum building.",
                invalidation="MACD histogram turns negative or RSI drops below 50.",
            )
        if 25 < rsi < 50 and macd_hist < 0 and macd_falling:
            strength = min(1.0, (50 - rsi) / 25 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.SELL,
                strength=strength,
                entry_low=round(close, 6),
                entry_high=round(close + 0.3 * atr, 6),
                stop_loss=round(close + 2.0 * atr, 6),
                take_profit_1=round(close - 1.5 * atr, 6),
                take_profit_2=round(close - 3.0 * atr, 6),
                reason=f"RSI at {rsi:.1f} (bearish zone, not oversold) with falling negative MACD histogram — downside momentum building.",
                invalidation="MACD histogram turns positive or RSI rises above 50.",
            )
        return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="RSI/MACD not aligned for a momentum entry.")
