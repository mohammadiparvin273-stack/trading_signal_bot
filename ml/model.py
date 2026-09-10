"""
Optional ML layer. Predicts P(price higher N bars later) using only
open-source, local libraries (scikit-learn / xgboost / lightgbm).

The core signal pipeline works with this fully disabled
(config/settings.py -> MLConfig.enabled = False); ML only adds a
probability score on top of the rule-based strategies.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config.settings import SETTINGS

FEATURE_COLUMNS = [
    "rsi_14", "atr_pct", "macd", "macd_hist", "bb_width", "bb_pctb",
    "adx_14", "return_1", "return_5", "return_20", "volume_z", "volatility_20",
]


def _build_model():
    model_type = SETTINGS.ml.model_type
    if model_type == "xgboost":
        import xgboost as xgb
        return xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
        )
    if model_type == "lightgbm":
        import lightgbm as lgb
        return lgb.LGBMClassifier(
            n_estimators=300, max_depth=-1, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, verbosity=-1,
        )
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05)


class SignalMLModel:
    def __init__(self):
        self.model = None
        self.trained_on_n_rows = 0

    def make_labels(self, df: pd.DataFrame, horizon: int = 5, threshold: float = 0.0) -> pd.Series:
        """Label = 1 if forward return over `horizon` bars beats `threshold`."""
        fwd_return = df["close"].shift(-horizon) / df["close"] - 1
        return (fwd_return > threshold).astype(int)

    def fit(self, df: pd.DataFrame, horizon: int = 5) -> None:
        labels = self.make_labels(df, horizon=horizon)
        data = df.copy()
        data["label"] = labels
        data = data.dropna(subset=FEATURE_COLUMNS + ["label"])
        if len(data) < SETTINGS.ml.min_train_bars:
            self.model = None
            return
        X = data[FEATURE_COLUMNS].values
        y = data["label"].values
        self.model = _build_model()
        self.model.fit(X, y)
        self.trained_on_n_rows = len(data)

    def predict_proba_up(self, df: pd.DataFrame) -> Optional[float]:
        if self.model is None:
            return None
        row = df.iloc[[-1]][FEATURE_COLUMNS]
        if row.isna().any(axis=None):
            return None
        proba = self.model.predict_proba(row.values)[0]
        classes = list(self.model.classes_)
        idx = classes.index(1) if 1 in classes else int(np.argmax(proba))
        return float(proba[idx])
