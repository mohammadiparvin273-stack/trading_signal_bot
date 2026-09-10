from __future__ import annotations

from aggregator.signal_aggregator import FinalSignal
from risk.risk_analysis import RiskAssessment
from strategies.base import Direction


def format_signal_message(sig: FinalSignal, risk: RiskAssessment | None) -> str:
    if sig.direction == Direction.NEUTRAL:
        return (
            f"⚪ NO TRADE / NEUTRAL\n"
            f"Asset: {sig.asset}  |  Timeframe: {sig.timeframe}\n"
            f"Market Regime: {sig.regime}\n"
            f"Signal ID: {sig.signal_id}\n"
            f"Timestamp: {sig.timestamp}\n\n"
            f"Reason: {sig.reason}\n\n"
            f"(This is informational only — no signal is being issued.)"
        )

    emoji = "🟢" if sig.direction == Direction.BUY else "🔴"
    lines = [
        f"{emoji} {sig.asset}",
        "",
        f"SIGNAL: {sig.direction.value}",
        f"Timeframe: {sig.timeframe}",
        f"Market Regime: {sig.regime}",
        "",
        f"Entry Zone: {sig.entry_low} – {sig.entry_high}",
        f"Stop Loss: {sig.stop_loss}",
        f"Take Profit 1: {sig.take_profit_1}",
        f"Take Profit 2: {sig.take_profit_2}",
        f"Risk/Reward: 1:{sig.risk_reward}" if sig.risk_reward else "Risk/Reward: N/A",
        "",
        f"Confidence: {sig.confidence}%",
        f"Strategy: {', '.join(sig.strategies)}",
    ]
    if sig.ml_probability is not None:
        lines.append(f"ML Probability: {sig.ml_probability}%")
    lines.append(f"LLM Sentiment: {sig.llm_sentiment}")

    if risk:
        lines += [
            "",
            f"Suggested Risk: {risk.suggested_risk_pct}% of account",
            f"Suggested Position Size: {risk.suggested_position_size}",
            f"Volatility (ATR): {risk.volatility_pct}%",
        ]
        if risk.exposure_warning:
            lines.append(f"⚠️ {risk.exposure_warning}")
        if risk.drawdown_warning:
            lines.append(f"⚠️ {risk.drawdown_warning}")

    lines += [
        "",
        f"Reason: {sig.reason}",
        f"Invalidation: {sig.invalidation}",
        "",
        f"Signal ID: {sig.signal_id} | {sig.timestamp}",
        "",
        "⚠️ This is an analytical suggestion only — NOT an executed trade. "
        "You decide whether to act on it manually.",
    ]
    return "\n".join(lines)
