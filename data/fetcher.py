"""Data connectivity helpers for OANDA v20."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import pandas as pd
import requests
from oandapyV20.exceptions import V20Error

from config.settings import DEFAULT_CANDLE_COUNT, OANDA_ACCOUNT_ID, OANDA_API_KEY, OANDA_ENV, validate_settings

SUPPORTED_PAIRS: set[str] = {"EUR_USD", "GBP_USD", "USD_JPY"}
SUPPORTED_GRANULARITIES: set[str] = {
    "M5",
    "M10",
    "M15",
    "M30",
    "H1",
    "H2",
    "H3",
    "H4",
    "H6",
    "H8",
    "H12",
    "D",
    "W",
    "M",
}


def get_oanda_client() -> oandapyV20.API:
    """Return an authenticated OANDA API client using values from settings."""
    validate_settings()
    return oandapyV20.API(access_token=OANDA_API_KEY, environment=OANDA_ENV)


def _validate_candle_request(pair: str, timeframe: str, count: int) -> None:
    """Validate candle request inputs."""
    if pair not in SUPPORTED_PAIRS:
        raise ValueError(f"Unsupported pair '{pair}'. Allowed: {sorted(SUPPORTED_PAIRS)}")

    if timeframe not in SUPPORTED_GRANULARITIES:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. Allowed: {sorted(SUPPORTED_GRANULARITIES)}"
        )

    if not 10 <= count <= 5000:
        raise ValueError("count must be between 10 and 5000")


def _normalize_oanda_candles(candles: list[dict[str, Any]]) -> pd.DataFrame:
    """Normalize OANDA candle payload to a typed OHLCV DataFrame.

    Incomplete candles are removed and output rows are sorted by time ascending.
    """
    records: list[dict[str, Any]] = []
    for candle in candles:
        if not candle.get("complete", False):
            continue

        mid: dict[str, str] = candle.get("mid", {})
        records.append(
            {
                "time": candle.get("time"),
                "open": float(mid.get("o", 0.0)),
                "high": float(mid.get("h", 0.0)),
                "low": float(mid.get("l", 0.0)),
                "close": float(mid.get("c", 0.0)),
                "volume": int(candle.get("volume", 0)),
            }
        )

    df = pd.DataFrame(records, columns=["time", "open", "high", "low", "close", "volume"])
    if df.empty:
        return df

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.astype(
        {
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "int64",
        }
    )
    return df.sort_values("time").reset_index(drop=True)


def get_candles(pair: str, timeframe: str = "M5", count: int = DEFAULT_CANDLE_COUNT) -> pd.DataFrame:
    """Fetch complete OANDA candles and return normalized OHLCV data.

    Retries transient request failures using exponential backoff with up to 3 attempts.
    """
    _validate_candle_request(pair=pair, timeframe=timeframe, count=count)

    client = get_oanda_client()
    params: dict[str, Any] = {"granularity": timeframe, "count": count, "price": "M"}
    endpoint = instruments.InstrumentsCandles(instrument=pair, params=params)

    delay_seconds = 0.5
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response: dict[str, Any] = client.request(endpoint)
            candles: list[dict[str, Any]] = response.get("candles", [])
            return _normalize_oanda_candles(candles)
        except (requests.exceptions.RequestException, TimeoutError, ConnectionError, V20Error):
            if attempt == max_retries:
                raise
            time.sleep(delay_seconds)
            delay_seconds *= 2

    return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])


def stream_price_tick(pair: str) -> dict[str, Any] | None:
    """Return the first streamed PRICE tick for a pair, or None if unavailable."""
    client = get_oanda_client()
    params = {"instruments": pair}
    endpoint = pricing.PricingStream(accountID=OANDA_ACCOUNT_ID, params=params)

    stream: Iterator[dict[str, Any]] = client.request(endpoint)
    for message in stream:
        if message.get("type") == "PRICE":
            return message
    return None
