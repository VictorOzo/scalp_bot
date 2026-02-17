
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure the directory that contains `data/`, `indicators/`, etc. is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def sample_ohlcv_df() -> pd.DataFrame:
    """Load deterministic OHLCV test fixture."""
    path = Path(__file__).resolve().parent / "fixtures" / "sample_ohlcv.csv"
    df = pd.read_csv(path)

    # Make parsing resilient to both "Z" and "+00:00"
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")

    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)

    df["volume"] = df["volume"].astype(int)
    return df