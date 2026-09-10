"""
Optional Deep Learning layer — a small feed-forward classifier (same
target as the ML layer: P(price higher N bars later)), built with
PyTorch. Fully optional:

- Disabled by default (config/settings.py -> DLConfig.enabled = False).
- `torch` is NOT in the default requirements.txt, so installing the
  base project never pulls in a heavy/GPU-oriented dependency.
- To use it: `pip install torch` (CPU build is fine and free) then set
  DLConfig.enabled = True.
- If enabled but torch isn't installed, this fails soft: predict_proba_up
  returns None and the aggregator just proceeds without a DL opinion —
  it never breaks the core signal pipeline.

Trains on CPU by default; on weak hardware this is a tiny model
(a couple thousand parameters) so it is fast even without a GPU.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config.settings import SETTINGS
from ml.model import FEATURE_COLUMNS


class SignalDLModel:
    def __init__(self):
        self.model = None
        self.mean_ = None
        self.std_ = None

    def _torch(self):
        try:
            import torch
            return torch
        except ImportError:
            return None

    def fit(self, df: pd.DataFrame, horizon: int = 5) -> None:
        torch = self._torch()
        if torch is None:
            self.model = None
            return

        import torch.nn as nn

        fwd_return = df["close"].shift(-horizon) / df["close"] - 1
        label = (fwd_return > 0).astype(int)
        data = df.copy()
        data["label"] = label
        data = data.dropna(subset=FEATURE_COLUMNS + ["label"])

        if len(data) < SETTINGS.dl.min_train_bars:
            self.model = None
            return

        X = data[FEATURE_COLUMNS].values.astype(np.float32)
        y = data["label"].values.astype(np.float32)

        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0) + 1e-8
        X_norm = (X - self.mean_) / self.std_

        X_t = torch.tensor(X_norm, dtype=torch.float32)
        y_t = torch.tensor(y, dtype=torch.float32).unsqueeze(1)

        n_features = X_t.shape[1]
        model = nn.Sequential(
            nn.Linear(n_features, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 1), nn.Sigmoid(),
        )
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = nn.BCELoss()

        model.train()
        for _ in range(SETTINGS.dl.epochs):
            optimizer.zero_grad()
            pred = model(X_t)
            loss = loss_fn(pred, y_t)
            loss.backward()
            optimizer.step()

        model.eval()
        self.model = model

    def predict_proba_up(self, df: pd.DataFrame) -> Optional[float]:
        torch = self._torch()
        if torch is None or self.model is None:
            return None
        row = df.iloc[[-1]][FEATURE_COLUMNS]
        if row.isna().any(axis=None):
            return None
        X = row.values.astype(np.float32)
        X_norm = (X - self.mean_) / self.std_
        with torch.no_grad():
            X_t = torch.tensor(X_norm, dtype=torch.float32)
            proba = self.model(X_t).item()
        return float(proba)
