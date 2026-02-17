"""Bollinger Band calculations."""

from __future__ import annotations

import pandas as pd


def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    """Return DataFrame with Bollinger Band columns.

    `bb_width` is defined as normalized width: `(bb_upper - bb_lower) / bb_mid`.
    """
    if period <= 0:
        raise ValueError("period must be positive")

    out = df.copy()
    out["bb_mid"] = out["close"].rolling(window=period, min_periods=period).mean()
    std = out["close"].rolling(window=period, min_periods=period).std(ddof=0)
    out["bb_upper"] = out["bb_mid"] + std_mult * std
    out["bb_lower"] = out["bb_mid"] - std_mult * std
    out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_mid"]
    return out
