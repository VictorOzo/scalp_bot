"""Average True Range using Wilder smoothing."""

from __future__ import annotations

import pandas as pd

from indicators._wilder import wilder_rma


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Return DataFrame with ATR column."""
    if period <= 0:
        raise ValueError("period must be positive")

    out = df.copy()
    prev_close = out["close"].shift(1)
    tr_components = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    out["atr"] = wilder_rma(tr.fillna(0.0), period)
    return out
