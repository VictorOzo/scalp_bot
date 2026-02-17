# scripts/run_phase3_console.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config.pairs import PAIR_STRATEGY_MAP
from config.settings import OANDA_ACCOUNT_ID

from data.fetcher import get_candles, get_oanda_client

from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap

from filters.market_state import get_market_state, is_strategy_allowed
from filters.news_filter import fetch_forexfactory_calendar, get_blocking_news_event
from filters.session_filter import SESSIONS, is_session_active
from filters.spread_filter import (
    MAX_SPREAD_PIPS,
    calculate_spread_pips,
    get_live_bid_ask,
    is_spread_acceptable,
)


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
    """
    Best-effort calendar fetch.
    If requests isn't installed or network fails, return None (offline-first behavior).
    """
    try:
        return fetch_forexfactory_calendar(timeout_s=5)
    except Exception:
        return None


def run_console() -> None:
    client = get_oanda_client()
    events = _safe_fetch_calendar()  # None => offline-first; gate will PASS

    print("\n" + "=" * 100)
    print("PHASE 3 DRY RUN — DATA + INDICATORS + GATES (with spread + news details)")
    print("=" * 100)

    now = datetime.now(timezone.utc)

    for pair, strategy_name in PAIR_STRATEGY_MAP.items():
        print("\n" + "-" * 100)
        print(f"PAIR: {pair} | STRATEGY: {strategy_name}")
        print(f"UTC now: {now.isoformat()}")

        df = get_candles(pair, timeframe="M5", count=200)
        df = compute_indicators(df)

        # Gate 1: Session
        session_ok = is_session_active(pair, now_utc=now)
        session_window = SESSIONS.get(pair)

        # Gate 2: Spread (live bid/ask + compute pips)
        bid, ask = get_live_bid_ask(pair, client, OANDA_ACCOUNT_ID)
        spread_pips = calculate_spread_pips(pair, bid, ask)
        max_spread = MAX_SPREAD_PIPS.get(pair, 2.0)
        spread_ok = is_spread_acceptable(pair, bid=bid, ask=ask)

        # Gate 3: News (High-impact only; print details if blocking)
        blocking_event = get_blocking_news_event(
            pair,
            now_utc=now,
            buffer_minutes=15,
            events=events,
        )
        news_ok = blocking_event is None

        # Gate 4: Enemy detector / market state
        market_state = get_market_state(df)
        enemy_ok = is_strategy_allowed(strategy_name, df)

        last = df.iloc[-1]

        print("\nGATE STATUS:")
        print(
            f"  Session Gate: {'PASS' if session_ok else 'BLOCK'} "
            f"(hour={now.hour}, window={session_window})"
        )
        print(
            f"  Spread  Gate: {'PASS' if spread_ok else 'BLOCK'} "
            f"(spread={spread_pips:.2f} pips, max={max_spread:.2f}) "
            f"(bid={bid:.5f}, ask={ask:.5f})"
        )
        if events is None:
            print("  News    Gate: PASS (calendar fetch unavailable => offline-first)")
        elif news_ok:
            print("  News    Gate: PASS (no HIGH impact within ±15 min)")
        else:
            print(
                "  News    Gate: BLOCK "
                f"({blocking_event.get('impact')} {blocking_event.get('country')}) "
                f"{blocking_event.get('title')} @ {blocking_event.get('date')}"
            )
        print(f"  Market State: {market_state}")
        print(f"  Enemy Check : {'PASS' if enemy_ok else 'BLOCK'}")

        print("\nLATEST CANDLE:")
        print(f"  Time: {last['time']}")
        print(
            f"  OHLC: {last['open']:.5f} / {last['high']:.5f} / "
            f"{last['low']:.5f} / {last['close']:.5f}"
        )

        print("\nINDICATORS (Last Candle):")
        fields = [
            "atr",
            "adx",
            "ema_fast",
            "ema_slow",
            "vwap",
            "rsi",
            "macd",
            "macd_signal",
            "bb_mid",
            "bb_upper",
            "bb_lower",
            "bb_width",
        ]

        for name in fields:
            value = last.get(name)
            if value is None or pd.isna(value):
                print(f"  {name:12s}: NaN")
            else:
                print(f"  {name:12s}: {float(value):.6f}")

        decision = (
            "READY FOR STRATEGY EVALUATION"
            if (session_ok and spread_ok and news_ok and enemy_ok)
            else "STAND DOWN (Gate Blocked)"
        )
        print(f"\nFINAL DECISION: {decision}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    run_console()
