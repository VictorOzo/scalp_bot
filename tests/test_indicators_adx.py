"""Tests for ADX and directional indicators."""

from __future__ import annotations

import numpy as np

from indicators.adx import calculate_adx


def test_adx_ranges(sample_ohlcv_df) -> None:
    out = calculate_adx(sample_ohlcv_df, period=14)
    valid_adx = out["adx"].dropna()
    assert ((valid_adx >= 0) & (valid_adx <= 100)).all()
    assert (out["plus_di"].dropna() >= 0).all()
    assert (out["minus_di"].dropna() >= 0).all()


def test_adx_known_points(sample_ohlcv_df) -> None:
    out = calculate_adx(sample_ohlcv_df, period=14)
    expected = {
        50: (50.6370422451, 8.9185411751, 1.0711071332),
        100: (41.7268030671, 8.3834526013, 1.5886434197),
        150: (43.3705700049, 9.1052559755, 1.0596315811),
    }

    for idx, (adx_val, plus_val, minus_val) in expected.items():
        assert np.isclose(out.loc[idx, "adx"], adx_val, atol=1e-6)
        assert np.isclose(out.loc[idx, "plus_di"], plus_val, atol=1e-6)
        assert np.isclose(out.loc[idx, "minus_di"], minus_val, atol=1e-6)
