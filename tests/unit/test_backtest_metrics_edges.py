from __future__ import annotations

import pandas as pd

from backtest.backtest import compute_metrics


def test_sharpe_zero_for_empty_trades() -> None:
    metrics = compute_metrics(pd.DataFrame(columns=["pnl_pips"]))
    assert metrics["sharpe"] == 0.0


def test_sharpe_zero_for_single_trade() -> None:
    trades = pd.DataFrame({"pnl_pips": [5.0]})
    metrics = compute_metrics(trades)
    assert metrics["sharpe"] == 0.0


def test_sharpe_zero_for_identical_returns() -> None:
    trades = pd.DataFrame({"pnl_pips": [2.0, 2.0, 2.0, 2.0]})
    metrics = compute_metrics(trades)
    assert metrics["sharpe"] == 0.0
