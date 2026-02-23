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
from storage.db import get_db_path
from storage.strategy_params import get_strategy_params_service


def get_effective_params() -> dict[str, float]:
    service = get_strategy_params_service(get_db_path())
    return dict(service.get("vwap_rsi").params)


def generate_signal_from_df(df: pd.DataFrame, *, params: dict[str, float] | None = None) -> str:
    """
    Gate 7 signal logic only.
    Assumes df contains: close, vwap, atr, rsi.
    Slightly loosened RSI thresholds and VWAP confirmation using ATR tolerance.
    """
    if len(df) < 30:
        return "HOLD"

    last = df.iloc[-1]

    close = float(last["close"])
    vwap = float(last["vwap"])
    rsi = float(last["rsi"])
    atr = float(last["atr"]) if pd.notna(last.get("atr")) else 0.0

    effective = params or get_effective_params()
    vwap_tol = float(effective["vwap_atr_tolerance"]) * atr

    if rsi < float(effective["rsi_buy_max"]) and close > (vwap - vwap_tol):
        return "BUY"
    if rsi > float(effective["rsi_sell_min"]) and close < (vwap + vwap_tol):
        return "SELL"
    return "HOLD"


def get_signal(client, account_id) -> str:
    """Full 7-gate strategy wrapper (Phase 4)."""
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

    params = get_effective_params()
    df = calculate_rsi(df, period=int(params["rsi_period"]))
    df = calculate_vwap(df)

    # 7) Signal logic
    return generate_signal_from_df(df, params=params)
