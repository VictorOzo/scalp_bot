"""Unit tests for spread filter."""

from __future__ import annotations

import pytest

from filters.spread_filter import calculate_spread_pips, is_spread_acceptable


def test_calculate_spread_pips_non_jpy_pair() -> None:
    assert calculate_spread_pips("EUR_USD", bid=1.1000, ask=1.1002) == pytest.approx(2.0)


def test_calculate_spread_pips_jpy_pair() -> None:
    assert calculate_spread_pips("USD_JPY", bid=150.00, ask=150.02) == pytest.approx(2.0)


def test_bad_prices_raise_value_error() -> None:
    with pytest.raises(ValueError):
        calculate_spread_pips("EUR_USD", bid=1.1000, ask=1.1000)


def test_is_spread_acceptable_uses_default_and_override() -> None:
    assert is_spread_acceptable("EUR_USD", bid=1.1000, ask=1.1001) is True
    assert is_spread_acceptable("EUR_USD", bid=1.1000, ask=1.1003) is False
    assert is_spread_acceptable("EUR_USD", bid=1.1000, ask=1.1003, max_spread_override=3.5) is True
