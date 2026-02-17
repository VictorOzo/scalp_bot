"""Internal helpers for Wilder-style smoothing."""

from __future__ import annotations

import pandas as pd


def wilder_rma(series: pd.Series, period: int) -> pd.Series:
    """Return Wilder's RMA for a series with optional warmup NaNs.

    The seed is the arithmetic mean of the first `period` non-NaN values.
    Values before the seed index are NaN.
    """
    if period <= 0:
        raise ValueError("period must be a positive integer")

    values = series.astype("float64")
    result = pd.Series(index=values.index, dtype="float64")

    valid_positions = [i for i, value in enumerate(values.tolist()) if pd.notna(value)]
    if len(valid_positions) < period:
        return result

    seed_position = valid_positions[period - 1]
    seed_window = [values.iloc[i] for i in valid_positions[:period]]
    result.iloc[seed_position] = sum(seed_window) / period

    for idx in range(seed_position + 1, len(values)):
        current = values.iloc[idx]
        prev = result.iloc[idx - 1]
        if pd.isna(current):
            result.iloc[idx] = prev
        else:
            result.iloc[idx] = ((period - 1) * prev + current) / period

    return result
