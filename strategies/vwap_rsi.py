"""VWAP + RSI strategy for USD_JPY."""

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
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap


def generate_signal_from_df(df: pd.DataFrame) -> str:
    """
    Pure signal logic (Gate 7).
    Assumes required indicators already exist: atr, vwap, rsi.
    Slightly loosened RSI thresholds and VWAP confirmation using ATR tolerance.
    """
    if len(df) < 30:
        return "HOLD"

    last = df.iloc[-1]

    close = float(last["close"])
    vwap = float(last["vwap"])
    rsi = float(last["rsi"])
    atr = float(last["atr"]) if pd.notna(last.get("atr")) else 0.0

    vwap_tol = 0.1 * atr  # loosened

    # loosened thresholds
    if rsi < 25 and close > (vwap - vwap_tol):
        return "BUY"
    if rsi > 75 and close < (vwap + vwap_tol):
        return "SELL"

    return "HOLD"


def get_signal(client, account_id) -> str:
    pair = "USD_JPY"

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

    # 6) Enemy detector gate (should block trending for this strategy)
    if not is_strategy_allowed("vwap_rsi", df):
        return "HOLD"

    df = calculate_rsi(df, period=3)
    df = calculate_vwap(df)

    # 7) Signal logic
    return generate_signal_from_df(df)
