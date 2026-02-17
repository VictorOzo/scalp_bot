"""Data connectivity helpers for OANDA v20."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import pandas as pd

from config.settings import (
    DEFAULT_CANDLE_COUNT,
    OANDA_ACCOUNT_ID,
    OANDA_API_KEY,
    OANDA_ENV,
    validate_settings,
)


def get_oanda_client() -> oandapyV20.API:
    """Create and return an authenticated OANDA API client."""
    validate_settings()
    return oandapyV20.API(access_token=OANDA_API_KEY, environment=OANDA_ENV)


def get_candles(
    pair: str,
    timeframe: str = "M5",
    count: int = DEFAULT_CANDLE_COUNT,
) -> pd.DataFrame:
    """Fetch candle data for a currency pair and return a normalized DataFrame."""
    client = get_oanda_client()
    params: dict[str, Any] = {
        "granularity": timeframe,
        "count": count,
        "price": "M",
    }
    endpoint = instruments.InstrumentsCandles(instrument=pair, params=params)
    response: dict[str, Any] = client.request(endpoint)

    candles: list[dict[str, Any]] = response.get("candles", [])
    records: list[dict[str, Any]] = []
    for candle in candles:
        mid: dict[str, str] = candle.get("mid", {})
        records.append(
            {
                "time": candle.get("time"),
                "open": float(mid.get("o", 0.0)),
                "high": float(mid.get("h", 0.0)),
                "low": float(mid.get("l", 0.0)),
                "close": float(mid.get("c", 0.0)),
                "volume": float(candle.get("volume", 0.0)),
            }
        )

    df = pd.DataFrame(records, columns=["time", "open", "high", "low", "close", "volume"])
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


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
