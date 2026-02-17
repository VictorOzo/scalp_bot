"""Unit tests for OANDA candle normalization."""

from __future__ import annotations

from data.fetcher import _normalize_oanda_candles


def test_normalize_filters_incomplete_and_types() -> None:
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
            "complete": False,
        },
    ]

    df = _normalize_oanda_candles(candles)

    assert len(df) == 1
    assert str(df["time"].dtype).startswith("datetime64[ns, UTC]")
    assert df["open"].dtype == "float64"
    assert df["volume"].dtype == "int64"
    assert df.iloc[0]["close"] == 1.1005
