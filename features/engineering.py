"""
Feature engineering built entirely from pandas/numpy — no paid data
vendor indicators required.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(close: pd.Series, period=20, std_mult=2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = (upper - lower) / mid
    return mid, upper, lower, width


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = _atr(df, period).replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx.fillna(0)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a broad, standard technical-feature set. Pure pandas/numpy."""
    out = df.copy()
    close = out["close"]

    out["ema_9"] = _ema(close, 9)
    out["ema_21"] = _ema(close, 21)
    out["ema_50"] = _ema(close, 50)
    out["ema_200"] = _ema(close, 200)

    out["rsi_14"] = _rsi(close, 14)
    out["atr_14"] = _atr(out, 14)
    out["atr_pct"] = out["atr_14"] / close

    macd_line, signal_line, hist = _macd(close)
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist

    bb_mid, bb_up, bb_low, bb_width = _bollinger(close)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_low
    out["bb_width"] = bb_width
    out["bb_pctb"] = (close - bb_low) / (bb_up - bb_low).replace(0, np.nan)

    out["adx_14"] = _adx(out, 14)

    out["donchian_high_20"] = out["high"].rolling(20).max()
    out["donchian_low_20"] = out["low"].rolling(20).min()

    out["return_1"] = close.pct_change(1)
    out["return_5"] = close.pct_change(5)
    out["return_20"] = close.pct_change(20)

    out["volume_z"] = (out["volume"] - out["volume"].rolling(50).mean()) / out["volume"].rolling(50).std()
    out["volatility_20"] = out["return_1"].rolling(20).std()

    out = out.dropna().reset_index(drop=True)
    return out
