"""Offline backtest runner for Phase 7."""

from __future__ import annotations

import argparse
import importlib

import pandas as pd

from backtest.backtest import backtest_strategy
from config.pairs import PAIR_STRATEGY_MAP


def _load_strategy_module(pair: str):
    strategy_name = PAIR_STRATEGY_MAP[pair]
    return importlib.import_module(f"strategies.{strategy_name}")


def _print_report(pair: str, mode: str, results: dict) -> None:
    train = results["train"]
    val = results["validation"]

    print(f"PAIR: {pair}")
    print(f"MODE: {mode}")

    if "hold_bars" in results and mode == "time_exit":
        print(f"hold_bars: {results['hold_bars']}")
    if "lookahead" in results and mode == "sl_tp":
        print(f"lookahead: {results['lookahead']}")

    print("TRAIN:")
    if "total_trades" in train:
        print(f"  total_trades: {train['total_trades']}")
        print(f"  wins: {train.get('wins', 'n/a')}")
        print(f"  losses: {train.get('losses', 'n/a')}")
    print(f"  win_rate: {train['win_rate']:.4f}")
    print(f"  profit_factor: {train['profit_factor']:.4f}")
    print(f"  sharpe: {train['sharpe']:.4f}")

    print("VALIDATION:")
    if "total_trades" in val:
        print(f"  total_trades: {val['total_trades']}")
        print(f"  wins: {val.get('wins', 'n/a')}")
        print(f"  losses: {val.get('losses', 'n/a')}")
    print(f"  win_rate: {val['win_rate']:.4f}")
    print(f"  profit_factor: {val['profit_factor']:.4f}")
    print(f"  sharpe: {val['sharpe']:.4f}")

    print(f"WIN RATE GAP: {results['gap']:.4f}")

    overfit = bool(results.get("overfit_warning", False))
    reason = results.get("overfit_reason", "")

    print(f"OVERFIT WARNING: {overfit}")
    if reason:
        print(f"OVERFIT REASON: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline backtests from CSV fixtures")
    parser.add_argument("--pair", choices=sorted(PAIR_STRATEGY_MAP.keys()), help="Single pair to run")
    parser.add_argument("--csv", required=True, help="Path to fixture CSV")
    parser.add_argument("--mode", choices=["sl_tp", "time_exit"], default="sl_tp")
    parser.add_argument("--hold-bars", type=int, default=5, help="Bars to hold in time_exit mode")
    parser.add_argument("--min-trades", type=int, default=30, help="Min trades per split for overfit warning")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    df["time"] = pd.to_datetime(df["time"], utc=True)

    pairs = [args.pair] if args.pair else list(PAIR_STRATEGY_MAP.keys())
    for idx, pair in enumerate(pairs):
        module = _load_strategy_module(pair)
        result = backtest_strategy(
            df.copy(),
            pair=pair,
            strategy_module=module,
            mode=args.mode,
            hold_bars=args.hold_bars,
            min_trades=args.min_trades,
        )
        _print_report(pair, args.mode, result)
        if idx != len(pairs) - 1:
            print()


if __name__ == "__main__":
    main()
