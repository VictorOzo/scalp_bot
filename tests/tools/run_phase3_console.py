from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config.pairs import PAIR_STRATEGY_MAP
from config.settings import OANDA_ACCOUNT_ID, OANDA_API_KEY
from data.fetcher import get_candles, get_oanda_client
from filters.market_state import get_market_state, is_strategy_allowed
from filters.news_filter import fetch_forexfactory_calendar, get_blocking_news_event
from filters.session_filter import SESSIONS, is_session_active
from filters.spread_filter import MAX_SPREAD_PIPS, calculate_spread_pips, get_live_bid_ask, is_spread_acceptable
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_atr(df)
    df = calculate_adx(df)
    df = calculate_ema(df)
    df = calculate_vwap(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger(df)
    return df


def _safe_fetch_calendar() -> list[dict[str, Any]] | None:
    try:
        return fetch_forexfactory_calendar(timeout_s=5)
    except Exception:
        return None


def _load_offline_fixture() -> pd.DataFrame:
    fixture = Path("tests/fixtures/sample_ohlcv.csv")
    df = pd.read_csv(fixture)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")
    return df


def run_console() -> None:
    live_mode = bool(OANDA_API_KEY and OANDA_ACCOUNT_ID)
    client = get_oanda_client() if live_mode else None
    events = _safe_fetch_calendar() if live_mode else None

    print("\n" + "=" * 100)
    print("PHASE 3/4 CONSOLE — CANDLES + INDICATORS + GATES")
    print(f"MODE: {'LIVE' if live_mode else 'OFFLINE FIXTURE'}")
    print("=" * 100)

    now = datetime.now(timezone.utc)

    for pair, strategy_name in PAIR_STRATEGY_MAP.items():
        print("\n" + "-" * 100)
        print(f"PAIR: {pair} | STRATEGY: {strategy_name}")
        print(f"UTC now: {now.isoformat()}")

        if live_mode:
            df = get_candles(pair, timeframe="M5", count=200)
            bid, ask = get_live_bid_ask(pair, client, OANDA_ACCOUNT_ID)
        else:
            df = _load_offline_fixture().tail(200).reset_index(drop=True)
            close = float(df["close"].iloc[-1])
            pip = 0.01 if pair.endswith("JPY") else 0.0001
            bid = close - pip * 0.5
            ask = close + pip * 0.5

        df = compute_indicators(df)

        session_ok = is_session_active(pair, now_utc=now)
        session_window = SESSIONS.get(pair)

        spread_pips = calculate_spread_pips(pair, bid, ask)
        max_spread = MAX_SPREAD_PIPS.get(pair, 2.0)
        spread_ok = is_spread_acceptable(pair, bid=bid, ask=ask)

        blocking_event = get_blocking_news_event(pair, now_utc=now, buffer_minutes=15, events=events)
        news_ok = blocking_event is None

        market_state = get_market_state(df)
        enemy_ok = is_strategy_allowed(strategy_name, df)

        last = df.iloc[-1]

        print("\nGATE STATUS:")
        print(f"  Session Gate: {'PASS' if session_ok else 'BLOCK'} (hour={now.hour}, window={session_window})")
        print(
            f"  Spread  Gate: {'PASS' if spread_ok else 'BLOCK'} (spread={spread_pips:.2f} pips, max={max_spread:.2f}) "
            f"(bid={bid:.5f}, ask={ask:.5f})"
        )
        if events is None:
            print("  News    Gate: PASS (calendar unavailable in current mode)")
        elif news_ok:
            print("  News    Gate: PASS (no HIGH impact within ±15 min)")
        else:
            print(
                "  News    Gate: BLOCK "
                f"({blocking_event.get('impact')} {blocking_event.get('country')}) "
                f"{blocking_event.get('title')} @ {blocking_event.get('date')}"
            )
        print(f"  Enemy   Gate: {'PASS' if enemy_ok else 'BLOCK'} (state={market_state})")

        print("\nLATEST CANDLE:")
        print(f"  Time: {last['time']}")
        print(f"  OHLC: {last['open']:.5f} / {last['high']:.5f} / {last['low']:.5f} / {last['close']:.5f}")

        print("\nINDICATORS (Last Candle):")
        for name in ["atr", "adx", "ema_fast", "ema_slow", "cross_up", "cross_down", "vwap", "rsi", "bb_upper", "bb_lower", "bb_width"]:
            value = last.get(name)
            if value is None or pd.isna(value):
                print(f"  {name:12s}: NaN")
            else:
                print(f"  {name:12s}: {value}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    run_console()
