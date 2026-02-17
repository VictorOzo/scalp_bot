"""Unit tests for market state enemy detector."""

from __future__ import annotations

import pandas as pd
import pytest

from filters.market_state import get_market_state, is_strategy_allowed


def _build_df(adx_last: float, atr_last: float, base_atr: float = 1.0) -> pd.DataFrame:
    atr_values = [base_atr] * 10 + [atr_last]
    adx_values = [22.0] * 10 + [adx_last]
    return pd.DataFrame({"adx": adx_values, "atr": atr_values})


def test_trending_when_adx_high_and_not_low_vol() -> None:
    df = _build_df(adx_last=35.0, atr_last=1.0)
    assert get_market_state(df) == "trending"


def test_weak_trend_when_adx_between_25_and_30() -> None:
    df = _build_df(adx_last=27.0, atr_last=1.0)
    assert get_market_state(df) == "weak_trend"


def test_ranging_when_adx_low() -> None:
    df = _build_df(adx_last=18.0, atr_last=1.0)
    assert get_market_state(df) == "ranging"


def test_ranging_when_low_vol_blocks_trending() -> None:
    df = _build_df(adx_last=35.0, atr_last=0.6)
    assert get_market_state(df) == "ranging"


def test_volatile_when_high_vol_and_low_adx() -> None:
    df = _build_df(adx_last=15.0, atr_last=1.5)
    assert get_market_state(df) == "volatile"


def test_is_strategy_allowed_mapping_and_volatile_block() -> None:
    trending_df = _build_df(adx_last=33.0, atr_last=1.0)
    ranging_df = _build_df(adx_last=15.0, atr_last=1.0)
    volatile_df = _build_df(adx_last=15.0, atr_last=1.5)

    assert is_strategy_allowed("ema_vwap", trending_df) is True
    assert is_strategy_allowed("vwap_rsi", trending_df) is False
    assert is_strategy_allowed("vwap_rsi", ranging_df) is True
    assert is_strategy_allowed("bb_breakout", volatile_df) is False


def test_missing_columns_raise_value_error() -> None:
    with pytest.raises(ValueError):
        get_market_state(pd.DataFrame({"adx": [20.0]}))
