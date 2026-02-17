"""Tests for Bollinger Bands."""

from __future__ import annotations

from indicators.bollinger import calculate_bollinger


def test_bollinger_relationships(sample_ohlcv_df) -> None:
    out = calculate_bollinger(sample_ohlcv_df)
    valid = out.dropna(subset=["bb_mid", "bb_upper", "bb_lower", "bb_width"])

    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_mid"] >= valid["bb_lower"]).all()
    assert (valid["bb_width"] >= 0).all()
