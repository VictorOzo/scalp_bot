"""Exponential moving average crossover indicator."""

from __future__ import annotations

import pandas as pd


def calculate_ema(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> pd.DataFrame:
    """Return EMA crossover columns using close prices."""
    if fast <= 0 or slow <= 0:
        raise ValueError("fast and slow periods must be positive")

    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=fast, adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=slow, adjust=False).mean()

    prev_fast = out["ema_fast"].shift(1)
    prev_slow = out["ema_slow"].shift(1)

    out["cross_up"] = (out["ema_fast"] > out["ema_slow"]) & (prev_fast <= prev_slow)
    out["cross_down"] = (out["ema_fast"] < out["ema_slow"]) & (prev_fast >= prev_slow)
    return out
