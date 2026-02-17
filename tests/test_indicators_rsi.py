"""Tests for RSI indicator."""

from __future__ import annotations

import numpy as np

from indicators.rsi import calculate_rsi


def test_rsi_range(sample_ohlcv_df) -> None:
    out = calculate_rsi(sample_ohlcv_df, period=3)
    valid = out["rsi"].dropna()
    assert ((valid >= 0) & (valid <= 100)).all()


def test_rsi_known_points(sample_ohlcv_df) -> None:
    out = calculate_rsi(sample_ohlcv_df, period=3)
    expected = {20: 20.5660073295, 50: 99.9694568527, 100: 99.9654704875}
    for idx, value in expected.items():
        assert np.isclose(out.loc[idx, "rsi"], value, atol=1e-6)
