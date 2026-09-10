"""
Walk-Forward Validation.

Splits history into rolling Train -> Validation -> Out-of-Sample windows
and re-runs the backtest on each OOS slice using an ML model trained
ONLY on data strictly before that slice (no leakage). A strategy/model
that looks good in-sample but falls apart out-of-sample is flagged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from backtest.backtester import BacktestResult, run_backtest
from features.engineering import build_features
from ml.model import SignalMLModel


@dataclass
class WalkForwardWindow:
    train_start: int
    train_end: int
    oos_start: int
    oos_end: int
    result: BacktestResult


def walk_forward_validate(df_raw: pd.DataFrame, train_bars: int = 1500,
                           oos_bars: int = 300, step_bars: int = 300,
                           use_ml: bool = True) -> List[WalkForwardWindow]:
    windows: List[WalkForwardWindow] = []
    n = len(df_raw)
    start = 0

    while start + train_bars + oos_bars <= n:
        train_end = start + train_bars
        oos_end = min(train_end + oos_bars, n)

        train_slice = df_raw.iloc[start:train_end].reset_index(drop=True)
        oos_slice_with_lookback = df_raw.iloc[max(0, train_end - 210):oos_end].reset_index(drop=True)

        ml_prob_series = None
        if use_ml:
            feats_train = build_features(train_slice)
            model = SignalMLModel()
            model.fit(feats_train)  # trained ONLY on data before the OOS window
            feats_oos = build_features(oos_slice_with_lookback)
            probs = []
            for k in range(len(feats_oos)):
                sub = feats_oos.iloc[: k + 1]
                p = model.predict_proba_up(sub) if model.model is not None else None
                probs.append(p if p is not None else 0.5)
            ml_prob_series = pd.Series(probs)

        result = run_backtest(oos_slice_with_lookback, ml_prob_series=ml_prob_series)
        windows.append(WalkForwardWindow(start, train_end, train_end, oos_end, result))

        start += step_bars

    return windows


def print_walk_forward_summary(windows: List[WalkForwardWindow]) -> None:
    print("=" * 60)
    print("WALK-FORWARD VALIDATION SUMMARY")
    print("=" * 60)
    for w in windows:
        r = w.result
        print(
            f"OOS bars [{w.oos_start}:{w.oos_end}] | "
            f"Signals={r.num_signals} Trades={len(r.trades)} "
            f"WinRate={r.win_rate}% PF={r.profit_factor} "
            f"Expectancy={r.expectancy}% MaxDD={r.max_drawdown}%"
        )
    if windows:
        avg_pf = sum(w.result.profit_factor for w in windows if w.result.profit_factor not in (0, float("inf"))) / max(1, len(windows))
        print("-" * 60)
        print(f"Average Profit Factor across OOS windows: {avg_pf:.2f}")
        print("If this is much lower than the in-sample/backtest PF, the")
        print("strategy is likely overfit — revisit thresholds/features.")
    print("=" * 60)
