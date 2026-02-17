"""EMA + VWAP strategy for EUR_USD."""

from __future__ import annotations

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
from indicators.ema import calculate_ema
from indicators.vwap import calculate_vwap


def generate_signal_from_df(df: pd.DataFrame) -> str:
    """
    Gate 7 signal logic only.
    Assumes df contains: close, vwap, atr, cross_up, cross_down.
    """
    if len(df) < 30:
        return "HOLD"

    last = df.iloc[-1]
    close = float(last["close"])
    vwap = float(last["vwap"])
    atr = float(last["atr"]) if pd.notna(last.get("atr")) else 0.0

    # Slightly loosen VWAP filter to allow near-VWAP crosses.
    vwap_tol = 0.2 * atr

    if bool(last["cross_up"]) and close > (vwap - vwap_tol):
        return "BUY"
    if bool(last["cross_down"]) and close < (vwap + vwap_tol):
        return "SELL"
    return "HOLD"


def get_signal(client, account_id) -> str:
    """Full 7-gate strategy wrapper (Phase 4)."""
    pair = "EUR_USD"

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

    # Fetch + indicators
    df = get_candles(pair, "M5", count=150)
    df = calculate_atr(df)
    df = calculate_adx(df)

    # 6) Enemy detector gate
    if not is_strategy_allowed("ema_vwap", df):
        return "HOLD"

    df = calculate_ema(df, fast=9, slow=21)
    df = calculate_vwap(df)

    # 7) Signal logic
    return generate_signal_from_df(df)
