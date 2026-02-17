"""Integration test for offline candle normalization and indicator computation."""

from __future__ import annotations

from data.fetcher import _normalize_oanda_candles
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr


def test_normalize_then_calculate_atr_adx_types_and_columns() -> None:
    candles = [
        {
            "time": "2024-01-01T00:00:00.000000000Z",
            "mid": {"o": "1.1000", "h": "1.1010", "l": "1.0990", "c": "1.1005"},
            "volume": 100,
            "complete": True,
        },
        {
            "time": "2024-01-01T00:05:00.000000000Z",
            "mid": {"o": "1.1005", "h": "1.1020", "l": "1.1000", "c": "1.1015"},
            "volume": 105,
            "complete": True,
        },
        {
            "time": "2024-01-01T00:10:00.000000000Z",
            "mid": {"o": "1.1015", "h": "1.1023", "l": "1.1008", "c": "1.1012"},
            "volume": 110,
            "complete": True,
        },
    ]

    normalized = _normalize_oanda_candles(candles)
    with_atr = calculate_atr(normalized)
    with_adx = calculate_adx(with_atr)

    assert "atr" in with_adx.columns
    assert "adx" in with_adx.columns
    assert with_adx["atr"].dtype == "float64"
    assert with_adx["adx"].dtype == "float64"
