"""
Risk Analysis — produces INFORMATIONAL numbers only:
suggested stop, suggested position size, R:R, exposure warnings.

This module never touches an exchange, never places or sizes a live
order. The user reads these numbers and decides everything manually.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config.settings import SETTINGS
from strategies.base import Direction


@dataclass
class RiskAssessment:
    suggested_risk_pct: float
    suggested_position_size: float
    risk_reward: Optional[float]
    volatility_pct: float
    drawdown_warning: Optional[str]
    exposure_warning: Optional[str]


def assess_risk(direction: Direction, entry_ref: float, stop_loss: float,
                 take_profit_1: float, atr_pct: float) -> RiskAssessment:
    risk_pct = SETTINGS.risk.max_risk_per_trade_pct
    equity = SETTINGS.risk.account_equity

    per_unit_risk = abs(entry_ref - stop_loss)
    if per_unit_risk <= 0:
        suggested_size = 0.0
    else:
        risk_amount = equity * (risk_pct / 100)
        suggested_size = round(risk_amount / per_unit_risk, 6)

    reward = abs(take_profit_1 - entry_ref)
    rr = round(reward / per_unit_risk, 2) if per_unit_risk > 0 else None

    drawdown_warning = None
    if atr_pct is not None and atr_pct > 0.05:
        drawdown_warning = f"High current volatility (ATR ≈ {atr_pct*100:.1f}% of price) — expect wider swings than usual."

    exposure_warning = None
    if rr is not None and rr < SETTINGS.risk.min_risk_reward:
        exposure_warning = (
            f"Risk/Reward ({rr}) is below the configured minimum "
            f"({SETTINGS.risk.min_risk_reward}) — consider skipping or tightening entry."
        )

    return RiskAssessment(
        suggested_risk_pct=risk_pct,
        suggested_position_size=suggested_size,
        risk_reward=rr,
        volatility_pct=round((atr_pct or 0) * 100, 2),
        drawdown_warning=drawdown_warning,
        exposure_warning=exposure_warning,
    )
