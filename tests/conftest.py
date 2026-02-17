"""Shared fixtures for indicator tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def sample_ohlcv_df() -> pd.DataFrame:
    """Load deterministic OHLCV test fixture."""
    path = Path(__file__).parent / "fixtures" / "sample_ohlcv.csv"
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)
    return df
