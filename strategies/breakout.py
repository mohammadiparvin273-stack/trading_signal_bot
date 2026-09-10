from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Direction, StrategyVote


class BreakoutStrategy(BaseStrategy):
    """Donchian-channel breakout with volume + volatility-expansion confirmation."""
    name = "Breakout"

    def evaluate(self, df: pd.DataFrame) -> StrategyVote:
        row = df.iloc[-1]
        prev = df.iloc[-2]
        close, atr = row["close"], row["atr_14"]
        donch_high, donch_low = prev["donchian_high_20"], prev["donchian_low_20"]
        vol_z = row["volume_z"]
        bb_width, bb_width_prev = row["bb_width"], prev["bb_width"]
        expanding_vol = bb_width > bb_width_prev

        if close > donch_high and vol_z > 0.5 and expanding_vol:
            strength = min(1.0, 0.4 + vol_z / 5)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.BUY,
                strength=strength,
                entry_low=round(donch_high, 6),
                entry_high=round(close, 6),
                stop_loss=round(donch_high - 1.0 * atr, 6),
                take_profit_1=round(close + 2.0 * atr, 6),
                take_profit_2=round(close + 4.0 * atr, 6),
                reason=f"Price broke above the 20-bar Donchian high ({donch_high:.6f}) with above-average volume and expanding volatility bands.",
                invalidation=f"Close back below the breakout level ({donch_high:.6f}).",
            )
        if close < donch_low and vol_z > 0.5 and expanding_vol:
            strength = min(1.0, 0.4 + vol_z / 5)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.SELL,
                strength=strength,
                entry_low=round(close, 6),
                entry_high=round(donch_low, 6),
                stop_loss=round(donch_low + 1.0 * atr, 6),
                take_profit_1=round(close - 2.0 * atr, 6),
                take_profit_2=round(close - 4.0 * atr, 6),
                reason=f"Price broke below the 20-bar Donchian low ({donch_low:.6f}) with above-average volume and expanding volatility bands.",
                invalidation=f"Close back above the breakdown level ({donch_low:.6f}).",
            )
        return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="No confirmed Donchian breakout with volume support.")
