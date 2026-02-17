"""VWAP + RSI strategy for USD_JPY."""

from __future__ import annotations

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


def get_signal(client, account_id) -> str:
    pair = "USD_JPY"

    if not is_session_active(pair):
        return "HOLD"
    if not is_spread_acceptable_live(pair, client, account_id):
        return "HOLD"
    if not is_news_clear(pair):
        return "HOLD"
    if has_open_position(pair, client, account_id):
        return "HOLD"
    if not is_within_daily_limit(client, account_id):
        return "HOLD"

    df = get_candles(pair, "M5", count=150)
    df = calculate_atr(df)
    df = calculate_adx(df)

    if not is_strategy_allowed("vwap_rsi", df):
        return "HOLD"

    df = calculate_rsi(df, period=3)
    df = calculate_vwap(df)

    last = df.iloc[-1]
    if float(last["rsi"]) < 20 and float(last["close"]) > float(last["vwap"]):
        return "BUY"
    if float(last["rsi"]) > 80 and float(last["close"]) < float(last["vwap"]):
        return "SELL"
    return "HOLD"
