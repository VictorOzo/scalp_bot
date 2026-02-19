from __future__ import annotations

import importlib
import socket

import pandas as pd

from backtest.backtest import backtest_strategy


REQUIRED_METRICS = {
    "total_trades",
    "win_rate",
    "profit_factor",
    "gross_win_pips",
    "gross_loss_pips",
    "max_drawdown",
    "sharpe",
    "avg_pips_per_trade",
}


def test_phase7_backtest_runs_offline_on_fixture(monkeypatch) -> None:
    def _block_network(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Network call attempted in offline backtest")

    monkeypatch.setattr(socket, "create_connection", _block_network)

    df = pd.read_csv("tests/fixtures/sample_ohlcv.csv")
    strategy = importlib.import_module("strategies.ema_vwap")

    result = backtest_strategy(df=df, pair="EUR_USD", strategy_module=strategy, mode="sl_tp")

    assert {"train", "validation", "gap", "overfit_warning"}.issubset(result.keys())
    assert REQUIRED_METRICS.issubset(result["train"].keys())
    assert REQUIRED_METRICS.issubset(result["validation"].keys())
    assert result["train"]["total_trades"] > 0
    assert isinstance(result["overfit_warning"], bool)
