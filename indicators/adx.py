"""Average Directional Index (ADX) with Wilder smoothing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators._wilder import wilder_rma


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Return DataFrame with ADX, +DI, and -DI columns."""
    if period <= 0:
        raise ValueError("period must be positive")

    out = df.copy()

    up_move = out["high"].diff()
    down_move = -out["low"].diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=out.index,
        dtype="float64",
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=out.index,
        dtype="float64",
    )

    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = wilder_rma(tr.fillna(0.0), period)
    plus_dm_smoothed = wilder_rma(plus_dm, period)
    minus_dm_smoothed = wilder_rma(minus_dm, period)

    out["plus_di"] = 100 * (plus_dm_smoothed / atr.replace(0.0, np.nan))
    out["minus_di"] = 100 * (minus_dm_smoothed / atr.replace(0.0, np.nan))

    di_sum = out["plus_di"] + out["minus_di"]
    dx = 100 * (out["plus_di"] - out["minus_di"]).abs() / di_sum.replace(0.0, np.nan)
    out["adx"] = wilder_rma(dx, period)
    return out
