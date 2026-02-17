"""Tests for ATR indicator."""

from __future__ import annotations

import numpy as np

from indicators.atr import calculate_atr


def test_atr_non_negative(sample_ohlcv_df) -> None:
    out = calculate_atr(sample_ohlcv_df, period=14)
    valid = out["atr"].dropna()
    assert (valid >= 0).all()


def test_atr_known_points(sample_ohlcv_df) -> None:
    out = calculate_atr(sample_ohlcv_df, period=14)
    expected = {20: 0.0019135077, 50: 0.0020558861, 100: 0.00192383}
    for idx, value in expected.items():
        assert np.isclose(out.loc[idx, "atr"], value, atol=1e-9)
