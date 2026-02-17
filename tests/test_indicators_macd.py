"""Tests for MACD."""

from __future__ import annotations

import numpy as np

from indicators.macd import calculate_macd


def test_macd_hist_identity(sample_ohlcv_df) -> None:
    out = calculate_macd(sample_ohlcv_df)
    assert np.allclose(out["macd_hist"], out["macd"] - out["macd_signal"], atol=1e-12)
