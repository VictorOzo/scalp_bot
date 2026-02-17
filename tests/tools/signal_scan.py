# tests/tools/signal_scan.py
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from config.pairs import PAIR_STRATEGY_MAP
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap

try:
    from data.fetcher import get_candles, get_oanda_client
    from config.settings import OANDA_ACCOUNT_ID
except Exception:
    get_candles = None  # type: ignore
    get_oanda_client = None  # type: ignore
    OANDA_ACCOUNT_ID = ""  # type: ignore


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ohlcv.csv"
DEFAULT_COUNT = 200
WARMUP = 60  # enough for BB(20), EMA(21), ADX/ATR(14), etc.


def _has_oanda_env() -> bool:
    return bool(os.getenv("OANDA_API_KEY")) and bool(os.getenv("OANDA_ACCOUNT_ID"))


def _load_fixture() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_PATH)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)
    return df.sort_values("time").reset_index(drop=True)


def _get_data(pair: str, count: int) -> tuple[str, pd.DataFrame]:
    if _has_oanda_env() and get_candles is not None:
        df = get_candles(pair, timeframe="M5", count=count)
        return "LIVE", df
    return "OFFLINE", _load_fixture().tail(count).reset_index(drop=True)


def _compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # Compute a superset so any strategy can use what it needs.
    df = calculate_atr(df)
    df = calculate_adx(df)
    df = calculate_ema(df)
    df = calculate_vwap(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger(df)
    return df


def _get_strategy_signal_fn(strategy_name: str) -> Callable[[pd.DataFrame], str]:
    """
    Expects strategies/<name>.py to export:
      generate_signal_from_df(df) -> "BUY"|"SELL"|"HOLD"
    """
    mod = import_module(f"strategies.{strategy_name}")
    fn = getattr(mod, "generate_signal_from_df", None)
    if not callable(fn):
        raise RuntimeError(
            f"strategies.{strategy_name} must export generate_signal_from_df(df) for scanning."
        )
    return fn


def scan_pair(pair: str, strategy_name: str, count: int) -> dict[str, Any]:
    mode, raw = _get_data(pair, count=count)
    df = _compute_all_indicators(raw)

    signal_fn = _get_strategy_signal_fn(strategy_name)

    counts: Counter[str] = Counter()
    first_idx = min(WARMUP, max(len(df) - 1, 0))

    for i in range(first_idx, len(df)):
        window = df.iloc[: i + 1].copy()
        sig = signal_fn(window)
        if sig not in {"BUY", "SELL", "HOLD"}:
            raise AssertionError(f"Invalid signal: {sig}")
        counts[sig] += 1

    last = df.iloc[-1]
    return {
        "pair": pair,
        "strategy": strategy_name,
        "mode": mode,
        "candles": len(df),
        "signals": dict(counts),
        "last_time": str(last["time"]),
        "last_close": float(last["close"]),
        "last_adx": float(last["adx"]) if pd.notna(last.get("adx")) else None,
        "last_atr": float(last["atr"]) if pd.notna(last.get("atr")) else None,
    }


def main() -> None:
    count = DEFAULT_COUNT
    now = datetime.now(timezone.utc).isoformat()

    print("\n" + "=" * 100)
    print("SIGNAL SCAN — last N candles (no trading)")
    print(f"UTC now: {now} | candles: {count} | warmup: {WARMUP}")
    print("=" * 100)

    for pair, strategy_name in PAIR_STRATEGY_MAP.items():
        res = scan_pair(pair, strategy_name, count=count)
        sig = res["signals"]
        print("\n" + "-" * 100)
        print(f"{res['pair']} | {res['strategy']} | MODE={res['mode']} | candles={res['candles']}")
        print(f"Signals: BUY={sig.get('BUY', 0)} SELL={sig.get('SELL', 0)} HOLD={sig.get('HOLD', 0)}")
        print(f"Last: time={res['last_time']} close={res['last_close']:.5f} adx={res['last_adx']} atr={res['last_atr']}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
