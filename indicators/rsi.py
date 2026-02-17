"""Relative Strength Index using Wilder smoothing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators._wilder import wilder_rma


def calculate_rsi(df: pd.DataFrame, period: int = 3) -> pd.DataFrame:
    """Return DataFrame with RSI values in [0, 100]."""
    if period <= 0:
        raise ValueError("period must be positive")

    out = df.copy()
    delta = out["close"].diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)

    avg_gain = wilder_rma(gains.fillna(0.0), period)
    avg_loss = wilder_rma(losses.fillna(0.0), period)

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))
    out.loc[avg_loss == 0, "rsi"] = 100.0
    out.loc[(avg_gain == 0) & (avg_loss == 0), "rsi"] = 50.0
    return out
