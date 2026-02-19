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


def _print_report(pair: str, mode: str, results: dict, hold_bars: int, lookahead: int) -> None:
    train = results["train"]
    val = results["validation"]

    train_total = int(train.get("total_trades", 0))
    train_wins = int(train.get("wins", round(float(train.get("win_rate", 0.0)) * train_total)))
    train_losses = int(train.get("losses", max(train_total - train_wins, 0)))

    val_total = int(val.get("total_trades", 0))
    val_wins = int(val.get("wins", round(float(val.get("win_rate", 0.0)) * val_total)))
    val_losses = int(val.get("losses", max(val_total - val_wins, 0)))

    print(f"PAIR: {pair}")
    print(f"MODE: {mode}")
    if mode == "time_exit":
        print(f"hold_bars: {hold_bars}")
    else:
        print(f"lookahead: {lookahead}")
    print("TRAIN:")
    print(f"  total_trades: {train_total}")
    print(f"  wins: {train_wins}")
    print(f"  losses: {train_losses}")
    print(f"  win_rate: {train['win_rate']:.4f}")
    print(f"  profit_factor: {train['profit_factor']:.4f}")
    print(f"  sharpe: {train['sharpe']:.4f}")
    print("VALIDATION:")
    print(f"  total_trades: {val_total}")
    print(f"  wins: {val_wins}")
    print(f"  losses: {val_losses}")
    print(f"  win_rate: {val['win_rate']:.4f}")
    print(f"  profit_factor: {val['profit_factor']:.4f}")
    print(f"  sharpe: {val['sharpe']:.4f}")
    print(f"WIN RATE GAP: {results['gap']:.4f}")
    reason = str(results.get("overfit_reason", ""))
    if reason:
        print(f"OVERFIT WARNING: {results['overfit_warning']} ({reason})")
    else:
        print(f"OVERFIT WARNING: {results['overfit_warning']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline backtests from CSV fixtures")
    parser.add_argument("--pair", choices=sorted(PAIR_STRATEGY_MAP.keys()), help="Single pair to run")
    parser.add_argument("--csv", required=True, help="Path to fixture CSV")
    parser.add_argument("--mode", choices=["sl_tp", "time_exit"], default="sl_tp")
    parser.add_argument("--hold-bars", type=int, default=5, help="Bars to hold in time_exit mode")
    parser.add_argument("--min-trades", type=int, default=30, help="Minimum trades required for overfit warning")
    parser.add_argument("--seed", type=int, default=123, help="Random seed for slippage simulation")
    parser.add_argument("--train-pct", type=float, default=0.7, help="Train split percentage in (0,1)")
    parser.add_argument("--lookahead", type=int, default=50, help="Lookahead bars in sl_tp mode")
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
            seed=args.seed,
            train_pct=args.train_pct,
            lookahead=args.lookahead,
        )
        _print_report(pair, args.mode, result, hold_bars=args.hold_bars, lookahead=args.lookahead)
        if idx != len(pairs) - 1:
            print()


if __name__ == "__main__":
    main()
