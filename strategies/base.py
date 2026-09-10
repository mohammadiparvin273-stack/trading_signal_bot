from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class StrategyVote:
    strategy_name: str
    direction: Direction
    strength: float          # 0..1 — how strongly this strategy believes in its call
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    reason: str = ""
    invalidation: str = ""


class BaseStrategy:
    name = "base"

    def evaluate(self, df) -> StrategyVote:
        raise NotImplementedError
