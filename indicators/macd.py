"""Moving Average Convergence Divergence (MACD)."""

from __future__ import annotations

import pandas as pd


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Return DataFrame with MACD line, signal line, and histogram."""
    if min(fast, slow, signal) <= 0:
        raise ValueError("fast, slow, and signal periods must be positive")

    out = df.copy()
    fast_ema = out["close"].ewm(span=fast, adjust=False).mean()
    slow_ema = out["close"].ewm(span=slow, adjust=False).mean()

    out["macd"] = fast_ema - slow_ema
    out["macd_signal"] = out["macd"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out
