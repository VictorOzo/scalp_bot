"""Volume-weighted average price with UTC daily reset."""

from __future__ import annotations

import pandas as pd


def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with a per-day VWAP column.

    VWAP uses typical price `(high + low + close) / 3` and resets on each UTC date.
    """
    out = df.copy()
    dates = out["time"].dt.floor("D")
    typical_price = (out["high"] + out["low"] + out["close"]) / 3.0
    tpv = typical_price * out["volume"]

    cumulative_tpv = tpv.groupby(dates).cumsum()
    cumulative_volume = out["volume"].groupby(dates).cumsum()
    out["vwap"] = cumulative_tpv / cumulative_volume
    return out
