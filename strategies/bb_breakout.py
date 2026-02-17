"""Bollinger breakout strategy for GBP_USD."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.fetcher import get_candles
from execution.order_manager import has_open_position
from execution.risk_manager import is_within_daily_limit
from filters.market_state import is_strategy_allowed
from filters.news_filter import is_news_clear
from filters.session_filter import is_session_active
from filters.spread_filter import is_spread_acceptable_live
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger


def generate_signal_from_df(df: pd.DataFrame) -> str:
    """
    Gate 7 signal logic only.
    Assumes df contains: close, volume, bb_upper, bb_lower, bb_width.
    """
    if len(df) < 25:
        return "HOLD"

    df["volume_mean20"] = df["volume"].rolling(20, min_periods=20).mean()
    df["volume_spike"] = df["volume"] > (df["volume_mean20"] * 1.2)  # loosened

    width_lookback = df["bb_width"].tail(100).dropna()
    if width_lookback.empty:
        return "HOLD"

    squeeze_threshold = float(np.percentile(width_lookback.to_numpy(), 35))  # loosened

    current = df.iloc[-1]
    prev = df.iloc[-2]

    squeeze_expand = (
        float(prev["bb_width"]) <= squeeze_threshold
        and float(current["bb_width"]) > float(prev["bb_width"]) * 1.02  # loosened
    )

    if (
        float(current["close"]) > float(current["bb_upper"])
        and bool(current["volume_spike"])
        and squeeze_expand
    ):
        return "BUY"

    if (
        float(current["close"]) < float(current["bb_lower"])
        and bool(current["volume_spike"])
        and squeeze_expand
    ):
        return "SELL"

    return "HOLD"


def get_signal(client, account_id) -> str:
    """Full 7-gate strategy wrapper (Phase 4)."""
    pair = "GBP_USD"

    # 1) Session gate
    if not is_session_active(pair):
        return "HOLD"
    # 2) Spread gate
    if not is_spread_acceptable_live(pair, client, account_id):
        return "HOLD"
    # 3) News gate
    if not is_news_clear(pair):
        return "HOLD"
    # 4) Open position gate
    if has_open_position(pair, client, account_id):
        return "HOLD"
    # 5) Daily loss limit gate
    if not is_within_daily_limit(client, account_id):
        return "HOLD"

    df = get_candles(pair, "M5", count=150)
    df = calculate_atr(df)
    df = calculate_adx(df)

    # 6) Enemy detector gate
    if not is_strategy_allowed("bb_breakout", df):
        return "HOLD"

    df = calculate_bollinger(df, period=20, std_mult=2.0)

    # 7) Signal logic
    return generate_signal_from_df(df)
