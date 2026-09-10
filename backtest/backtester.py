"""
Backtests the SIGNAL strategy (not an execution simulator for real
trading) — it measures how the signals *would have* performed, purely
for research/evaluation. It never sends orders anywhere.

Guards against the classic pitfalls:
- Look-ahead bias: features/regime/votes for bar i only ever use data
  up to and including bar i; entries are simulated on bar i+1.
- Data leakage: ML model is trained walk-forward-style, never fit on
  data that includes the bar(s) being evaluated (see walk_forward.py).
- Transaction cost + slippage: subtracted from every simulated trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from aggregator.signal_aggregator import aggregate
from features.engineering import build_features
from llm.sentiment import Sentiment
from regime.detector import detect_regime
from strategies.base import Direction
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy

STRATEGIES = [TrendFollowingStrategy(), MomentumStrategy(), BreakoutStrategy(), MeanReversionStrategy()]


@dataclass
class Trade:
    entry_index: int
    exit_index: int
    direction: str
    entry_price: float
    exit_price: float
    result: str      # "TP1", "TP2", "SL", "TIMEOUT"
    pnl_pct: float


@dataclass
class BacktestResult:
    trades: List[Trade]
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    sharpe: float
    sortino: float
    avg_win: float
    avg_loss: float
    avg_win_pct_on_tp1: float
    num_signals: int
    false_signal_rate: float


def run_backtest(df_raw: pd.DataFrame, asset: str = "BACKTEST", timeframe: str = "1h",
                  transaction_cost_pct: float = 0.04, slippage_pct: float = 0.03,
                  max_holding_bars: int = 60, ml_prob_series: Optional[pd.Series] = None) -> BacktestResult:
    feats = build_features(df_raw)
    trades: List[Trade] = []
    signals_seen = 0
    false_signals = 0  # signals that never reach TP1 nor hit a clean SL within horizon (ambiguous/chop)

    min_lookback = 210  # enough bars for EMA200 etc. to be valid
    for i in range(min_lookback, len(feats) - 1):
        window = feats.iloc[: i + 1]  # only data up to and including bar i -> no look-ahead
        row = window.iloc[-1]
        regime = detect_regime(row)
        votes = [s.evaluate(window) for s in STRATEGIES]

        ml_prob = float(ml_prob_series.iloc[i]) if ml_prob_series is not None else None
        signal = aggregate(asset, timeframe, regime, votes, ml_prob, Sentiment.NEUTRAL)

        if signal.direction == Direction.NEUTRAL:
            continue

        signals_seen += 1
        entry_bar = i + 1  # simulate fill on the NEXT bar's open (no look-ahead)
        if entry_bar >= len(feats):
            continue
        entry_price = feats.iloc[entry_bar]["open"]
        # Apply slippage against us on entry
        entry_price *= (1 + slippage_pct / 100) if signal.direction == Direction.BUY else (1 - slippage_pct / 100)

        trade = _simulate_trade(feats, entry_bar, entry_price, signal, max_holding_bars, transaction_cost_pct, slippage_pct)
        if trade:
            trades.append(trade)
            if trade.result == "TIMEOUT":
                false_signals += 1

    return _compute_metrics(trades, signals_seen, false_signals)


def _simulate_trade(feats: pd.DataFrame, entry_bar: int, entry_price: float, signal,
                     max_holding_bars: int, cost_pct: float, slippage_pct: float) -> Optional[Trade]:
    direction = signal.direction
    stop = signal.stop_loss
    tp1 = signal.take_profit_1

    end_bar = min(entry_bar + max_holding_bars, len(feats) - 1)
    for j in range(entry_bar, end_bar + 1):
        bar = feats.iloc[j]
        if direction == Direction.BUY:
            hit_sl = bar["low"] <= stop
            hit_tp = bar["high"] >= tp1
        else:
            hit_sl = bar["high"] >= stop
            hit_tp = bar["low"] <= tp1

        if hit_sl and hit_tp:
            # Conservative assumption: stop hit first within the same bar
            exit_price = stop
            result = "SL"
        elif hit_sl:
            exit_price = stop
            result = "SL"
        elif hit_tp:
            exit_price = tp1
            result = "TP1"
        else:
            continue

        exit_price *= (1 - slippage_pct / 100) if direction == Direction.BUY else (1 + slippage_pct / 100)
        pnl_pct = ((exit_price - entry_price) / entry_price) if direction == Direction.BUY else \
                  ((entry_price - exit_price) / entry_price)
        pnl_pct -= (cost_pct / 100) * 2  # round-trip transaction cost
        return Trade(entry_bar, j, direction.value, entry_price, exit_price, result, pnl_pct * 100)

    # Timed out without hitting SL or TP1 -> close at last available price
    last = feats.iloc[end_bar]
    exit_price = last["close"]
    pnl_pct = ((exit_price - entry_price) / entry_price) if direction == Direction.BUY else \
              ((entry_price - exit_price) / entry_price)
    pnl_pct -= (cost_pct / 100) * 2
    return Trade(entry_bar, end_bar, direction.value, entry_price, exit_price, "TIMEOUT", pnl_pct * 100)


def _compute_metrics(trades: List[Trade], signals_seen: int, false_signals: int) -> BacktestResult:
    if not trades:
        return BacktestResult(
            trades=[], win_rate=0, profit_factor=0, expectancy=0, max_drawdown=0,
            sharpe=0, sortino=0, avg_win=0, avg_loss=0, avg_win_pct_on_tp1=0,
            num_signals=signals_seen, false_signal_rate=0,
        )

    pnl = np.array([t.pnl_pct for t in trades])
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    win_rate = len(wins) / len(pnl) * 100
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = abs(losses.sum()) if len(losses) else 1e-9
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")
    expectancy = pnl.mean()

    equity_curve = np.cumsum(pnl)
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = equity_curve - running_max
    max_drawdown = drawdown.min()

    std = pnl.std(ddof=1) if len(pnl) > 1 else 1e-9
    sharpe = (pnl.mean() / std) * np.sqrt(252) if std else 0.0
    downside_std = losses.std(ddof=1) if len(losses) > 1 else 1e-9
    sortino = (pnl.mean() / downside_std) * np.sqrt(252) if downside_std else 0.0

    tp1_pnls = [t.pnl_pct for t in trades if t.result == "TP1"]
    avg_win_pct_on_tp1 = float(np.mean(tp1_pnls)) if tp1_pnls else 0.0

    false_signal_rate = (false_signals / signals_seen * 100) if signals_seen else 0.0

    return BacktestResult(
        trades=trades,
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        expectancy=round(expectancy, 4),
        max_drawdown=round(max_drawdown, 2),
        sharpe=round(sharpe, 2),
        sortino=round(sortino, 2),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        avg_win_pct_on_tp1=round(avg_win_pct_on_tp1, 2),
        num_signals=signals_seen,
        false_signal_rate=round(false_signal_rate, 2),
    )


def print_report(result: BacktestResult) -> None:
    print("=" * 50)
    print("BACKTEST REPORT")
    print("=" * 50)
    print(f"Signals generated : {result.num_signals}")
    print(f"Trades taken      : {len(result.trades)}")
    print(f"Win Rate          : {result.win_rate}%")
    print(f"Profit Factor     : {result.profit_factor}")
    print(f"Expectancy/trade  : {result.expectancy}%")
    print(f"Max Drawdown      : {result.max_drawdown}%")
    print(f"Sharpe Ratio      : {result.sharpe}")
    print(f"Sortino Ratio     : {result.sortino}")
    print(f"Avg Win           : {result.avg_win}%")
    print(f"Avg Loss          : {result.avg_loss}%")
    print(f"Avg % gain on TP1 hits : {result.avg_win_pct_on_tp1}%")
    print(f"False Signal Rate : {result.false_signal_rate}%")
    print("=" * 50)
