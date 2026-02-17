"""Integration tests for Phase 1-3 indicator and gate pipeline."""

from __future__ import annotations

import pandas as pd

from filters.market_state import VALID_STATES, get_market_state, is_strategy_allowed
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr


def test_pipeline_indicators_then_market_state() -> None:
    df = pd.read_csv("tests/fixtures/sample_ohlcv.csv")

    with_atr = calculate_atr(df)
    with_adx = calculate_adx(with_atr)

    assert "atr" in with_adx.columns
    assert "adx" in with_adx.columns

    state = get_market_state(with_adx)
    assert state in VALID_STATES

    ema_allowed = is_strategy_allowed("ema_vwap", with_adx)
    vwap_rsi_allowed = is_strategy_allowed("vwap_rsi", with_adx)
    assert isinstance(ema_allowed, bool)
    assert isinstance(vwap_rsi_allowed, bool)
