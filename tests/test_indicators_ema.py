"""Tests for EMA crossover calculations."""

from __future__ import annotations

from indicators.ema import calculate_ema


def test_ema_columns_exist(sample_ohlcv_df) -> None:
    out = calculate_ema(sample_ohlcv_df)
    for col in ["ema_fast", "ema_slow", "cross_up", "cross_down"]:
        assert col in out.columns


def test_ema_crosses_occur_on_crossing_candle(sample_ohlcv_df) -> None:
    out = calculate_ema(sample_ohlcv_df)

    prev_fast = out["ema_fast"].shift(1)
    prev_slow = out["ema_slow"].shift(1)
    expected_up = (out["ema_fast"] > out["ema_slow"]) & (prev_fast <= prev_slow)
    expected_down = (out["ema_fast"] < out["ema_slow"]) & (prev_fast >= prev_slow)

    assert out["cross_up"].equals(expected_up)
    assert out["cross_down"].equals(expected_down)


def test_ema_no_lookahead_flags(sample_ohlcv_df) -> None:
    out = calculate_ema(sample_ohlcv_df)
    assert not ((out["cross_up"] | out["cross_down"]) & out["ema_fast"].isna()).any()
