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
    print("TRAIN:")
    print(f"  win_rate: {train['win_rate']:.4f}")
    print(f"  profit_factor: {train['profit_factor']:.4f}")
    print(f"  sharpe: {train['sharpe']:.4f}")
    print("VALIDATION:")
    print(f"  win_rate: {val['win_rate']:.4f}")
    print(f"  profit_factor: {val['profit_factor']:.4f}")
    print(f"  sharpe: {val['sharpe']:.4f}")
    print(f"WIN RATE GAP: {results['gap']:.4f}")
    print(f"OVERFIT WARNING: {results['overfit_warning']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline backtests from CSV fixtures")
    parser.add_argument("--pair", choices=sorted(PAIR_STRATEGY_MAP.keys()), help="Single pair to run")
    parser.add_argument("--csv", required=True, help="Path to fixture CSV")
    parser.add_argument("--mode", choices=["sl_tp", "time_exit"], default="sl_tp")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    df["time"] = pd.to_datetime(df["time"], utc=True)

    pairs = [args.pair] if args.pair else list(PAIR_STRATEGY_MAP.keys())
    for idx, pair in enumerate(pairs):
        module = _load_strategy_module(pair)
        result = backtest_strategy(df.copy(), pair=pair, strategy_module=module, mode=args.mode)
        _print_report(pair, args.mode, result)
        if idx != len(pairs) - 1:
            print()


if __name__ == "__main__":
    main()
