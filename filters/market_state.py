"""Market regime classification and strategy gating."""

from __future__ import annotations

import numpy as np
import pandas as pd

VALID_STATES: set[str] = {"trending", "weak_trend", "ranging", "volatile"}


def get_market_state(df: pd.DataFrame, lookback: int = 200) -> str:
    """Classify market state from pre-computed ADX and ATR columns."""
    required_columns = {"adx", "atr"}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    atr_series = df["atr"].dropna()
    adx_series = df["adx"].dropna()
    if atr_series.empty or adx_series.empty:
        raise ValueError("ADX and ATR data must contain at least one non-NaN value")

    atr_window = atr_series.tail(lookback)
    atr_median = float(np.percentile(atr_window.to_numpy(), 50))
    atr_last = float(atr_series.iloc[-1])
    adx_last = float(adx_series.iloc[-1])

    low_vol = atr_last < atr_median * 0.7
    high_vol = atr_last > atr_median * 1.3

    if high_vol and adx_last < 20:
        return "volatile"

    if low_vol:
        return "ranging"

    if adx_last >= 30:
        return "trending"
    if adx_last >= 25:
        return "weak_trend"
    return "ranging"


def is_strategy_allowed(strategy_name: str, df: pd.DataFrame) -> bool:
    """Return whether a strategy is allowed in the current market state."""
    state = get_market_state(df)
    if state == "volatile":
        return False

    if strategy_name == "ema_vwap":
        return state in {"trending", "weak_trend"}
    if strategy_name == "vwap_rsi":
        return state == "ranging"
    if strategy_name == "bb_breakout":
        return True
    return False
