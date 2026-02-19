from __future__ import annotations

import random

import pandas as pd

from backtest.backtest import simulate_trade


def test_buy_sl_hit_and_cost_applied() -> None:
    future = pd.DataFrame([
        {"high": 1.1010, "low": 1.0990, "close": 1.1005},
    ])
    result, pnl, entry = simulate_trade(
        future_df=future,
        direction="BUY",
        raw_entry=1.1000,
        sl=1.0995,
        tp=1.1015,
        pair="EUR_USD",
        rng=random.Random(0),
    )
    assert result == "LOSS"
    assert pnl < 0
    assert entry != 1.1000


def test_buy_tp_hit() -> None:
    future = pd.DataFrame([
        {"high": 1.1020, "low": 1.1001, "close": 1.1017},
    ])
    result, pnl, _ = simulate_trade(
        future_df=future,
        direction="BUY",
        raw_entry=1.1000,
        sl=1.0990,
        tp=1.1015,
        pair="EUR_USD",
        rng=random.Random(0),
    )
    assert result == "WIN"
    assert pnl > 0


def test_sell_sl_hit() -> None:
    future = pd.DataFrame([
        {"high": 1.1015, "low": 1.0995, "close": 1.1008},
    ])
    result, pnl, _ = simulate_trade(
        future_df=future,
        direction="SELL",
        raw_entry=1.1000,
        sl=1.1010,
        tp=1.0990,
        pair="EUR_USD",
        rng=random.Random(0),
    )
    assert result == "LOSS"
    assert pnl < 0


def test_sell_tp_hit() -> None:
    future = pd.DataFrame([
        {"high": 1.1002, "low": 1.0988, "close": 1.0992},
    ])
    result, pnl, _ = simulate_trade(
        future_df=future,
        direction="SELL",
        raw_entry=1.1000,
        sl=1.1010,
        tp=1.0990,
        pair="EUR_USD",
        rng=random.Random(0),
    )
    assert result == "WIN"
    assert pnl > 0


def test_timeout_result() -> None:
    future = pd.DataFrame([
        {"high": 1.1004, "low": 1.0998, "close": 1.1001},
        {"high": 1.1003, "low": 1.0999, "close": 1.1002},
    ])
    result, _, _ = simulate_trade(
        future_df=future,
        direction="BUY",
        raw_entry=1.1000,
        sl=1.0990,
        tp=1.1010,
        pair="EUR_USD",
        rng=random.Random(0),
    )
    assert result == "TIMEOUT"
