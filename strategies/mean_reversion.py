from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy, Direction, StrategyVote


class MeanReversionStrategy(BaseStrategy):
    """Bollinger %B + RSI extremes, only fired in non-trending (ranging) regimes."""
    name = "Mean Reversion"

    def evaluate(self, df: pd.DataFrame) -> StrategyVote:
        row = df.iloc[-1]
        close, atr, rsi = row["close"], row["atr_14"], row["rsi_14"]
        pctb = row["bb_pctb"]
        bb_mid = row["bb_mid"]
        adx = row["adx_14"]

        # Mean reversion is only valid when there's no strong trend to fight.
        if adx >= 25:
            return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="Trend too strong for mean-reversion setups.")

        if pctb <= 0.05 and rsi < 32:
            strength = min(1.0, (32 - rsi) / 32 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.BUY,
                strength=strength,
                entry_low=round(close - 0.2 * atr, 6),
                entry_high=round(close, 6),
                stop_loss=round(close - 1.8 * atr, 6),
                take_profit_1=round(bb_mid, 6),
                take_profit_2=round(row["bb_upper"], 6),
                reason=f"Price touched lower Bollinger Band (%B={pctb:.2f}) with oversold RSI ({rsi:.1f}) in a ranging market.",
                invalidation="Close decisively below the lower band (band-walk / regime shift to trend).",
            )
        if pctb >= 0.95 and rsi > 68:
            strength = min(1.0, (rsi - 68) / 32 * 0.6 + 0.3)
            return StrategyVote(
                strategy_name=self.name,
                direction=Direction.SELL,
                strength=strength,
                entry_low=round(close, 6),
                entry_high=round(close + 0.2 * atr, 6),
                stop_loss=round(close + 1.8 * atr, 6),
                take_profit_1=round(bb_mid, 6),
                take_profit_2=round(row["bb_lower"], 6),
                reason=f"Price touched upper Bollinger Band (%B={pctb:.2f}) with overbought RSI ({rsi:.1f}) in a ranging market.",
                invalidation="Close decisively above the upper band (band-walk / regime shift to trend).",
            )
        return StrategyVote(self.name, Direction.NEUTRAL, 0.0, reason="No Bollinger/RSI extreme in range regime.")
