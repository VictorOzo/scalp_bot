"""Tests for daily-reset VWAP."""

from __future__ import annotations

import numpy as np

from indicators.vwap import calculate_vwap


def test_vwap_resets_on_new_date(sample_ohlcv_df) -> None:
    out = calculate_vwap(sample_ohlcv_df)
    day_change = out["time"].dt.date != out["time"].shift(1).dt.date
    first_rows = out[day_change]

    for idx in first_rows.index:
        tp = (out.loc[idx, "high"] + out.loc[idx, "low"] + out.loc[idx, "close"]) / 3.0
        assert np.isclose(out.loc[idx, "vwap"], tp)


def test_vwap_is_between_running_daily_tp_extremes(sample_ohlcv_df) -> None:
    out = calculate_vwap(sample_ohlcv_df)
    dates = out["time"].dt.floor("D")
    tp = (out["high"] + out["low"] + out["close"]) / 3.0

    running_min = tp.groupby(dates).cummin()
    running_max = tp.groupby(dates).cummax()

    assert ((out["vwap"] >= running_min) & (out["vwap"] <= running_max)).all()
