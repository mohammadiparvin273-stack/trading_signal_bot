"""
Entry point.

Usage:
    python main.py backtest --symbol BTC/USDT --timeframe 1h --bars 3000
    python main.py walk-forward --symbol BTC/USDT --timeframe 1h --bars 4000
    python main.py paper-signal              # loop, PAPER_SIGNAL mode
    python main.py live-signal               # loop, LIVE_SIGNAL mode (still signal-only!)
    python main.py once                      # single pass over configured symbols

IMPORTANT: "live-signal" does NOT execute trades. In this project there
is no execution mode at all — LIVE_SIGNAL only means "generate signals
from live market data," same as PAPER_SIGNAL. Nothing here ever calls
an exchange's order-placement endpoints.
"""
from __future__ import annotations

import argparse
import time

from config.settings import SETTINGS
from data.fetcher import MarketDataFetcher
from pipeline import SignalPipeline


def cmd_backtest(args):
    from backtest.backtester import print_report, run_backtest

    fetcher = MarketDataFetcher()
    print(f"Fetching {args.bars} bars of {args.symbol} @ {args.timeframe} (free public data)...")
    df = fetcher.fetch_ohlcv_history(args.symbol, args.timeframe, args.bars)
    result = run_backtest(df, asset=args.symbol, timeframe=args.timeframe)
    print_report(result)


def cmd_walk_forward(args):
    from backtest.walk_forward import print_walk_forward_summary, walk_forward_validate

    fetcher = MarketDataFetcher()
    print(f"Fetching {args.bars} bars of {args.symbol} @ {args.timeframe} for walk-forward validation...")
    df = fetcher.fetch_ohlcv_history(args.symbol, args.timeframe, args.bars)
    windows = walk_forward_validate(df, train_bars=args.train_bars, oos_bars=args.oos_bars, step_bars=args.step_bars)
    print_walk_forward_summary(windows)


def cmd_dashboard(args):
    from dashboard.generate_dashboard import generate
    path = generate()
    print(f"Dashboard written to {path}")


def cmd_once(args):
    pipeline = SignalPipeline()
    for symbol in SETTINGS.run.symbols:
        print(f"\nProcessing {symbol}...")
        pipeline.process_and_notify(symbol)


def cmd_loop(args, mode: str):
    SETTINGS.run.mode = mode
    pipeline = SignalPipeline()
    print(f"Starting {mode} loop | symbols={SETTINGS.run.symbols} | timeframe={SETTINGS.run.timeframe} "
          f"| poll every {SETTINGS.run.poll_seconds}s | Ctrl+C to stop")
    print("NOTE: this mode only ever produces signals. No orders are placed.")
    try:
        while True:
            for symbol in SETTINGS.run.symbols:
                try:
                    pipeline.process_and_notify(symbol)
                except Exception as e:
                    print(f"[error] {symbol}: {e}")
            time.sleep(SETTINGS.run.poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="Trading SIGNAL Bot (analysis-only, no execution)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bt = sub.add_parser("backtest")
    p_bt.add_argument("--symbol", default=SETTINGS.run.symbols[0])
    p_bt.add_argument("--timeframe", default=SETTINGS.run.timeframe)
    p_bt.add_argument("--bars", type=int, default=3000)
    p_bt.set_defaults(func=cmd_backtest)

    p_wf = sub.add_parser("walk-forward")
    p_wf.add_argument("--symbol", default=SETTINGS.run.symbols[0])
    p_wf.add_argument("--timeframe", default=SETTINGS.run.timeframe)
    p_wf.add_argument("--bars", type=int, default=4000)
    p_wf.add_argument("--train-bars", type=int, default=1500)
    p_wf.add_argument("--oos-bars", type=int, default=300)
    p_wf.add_argument("--step-bars", type=int, default=300)
    p_wf.set_defaults(func=cmd_walk_forward)

    p_once = sub.add_parser("once")
    p_once.set_defaults(func=cmd_once)

    p_dash = sub.add_parser("dashboard")
    p_dash.set_defaults(func=cmd_dashboard)

    p_paper = sub.add_parser("paper-signal")
    p_paper.set_defaults(func=lambda a: cmd_loop(a, "PAPER_SIGNAL"))

    p_live = sub.add_parser("live-signal")
    p_live.set_defaults(func=lambda a: cmd_loop(a, "LIVE_SIGNAL"))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
