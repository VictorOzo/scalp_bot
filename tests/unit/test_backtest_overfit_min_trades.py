from __future__ import annotations

import pandas as pd

import backtest.backtest as bt


class _DummyStrategy:
    @staticmethod
    def generate_signal_from_df(_df: pd.DataFrame) -> str:
        return "HOLD"


def test_overfit_disabled_when_insufficient_trades(monkeypatch) -> None:
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        return df

    calls = {"n": 0}

    def _run_segment_ordered(*args, **kwargs) -> pd.DataFrame:
        calls["n"] += 1
        if calls["n"] == 1:
            return pd.DataFrame({"pnl_pips": [1.0] * 10})
        return pd.DataFrame({"pnl_pips": [-1.0] * 12})

    monkeypatch.setattr(bt, "_prepare_indicators", _prepare)
    monkeypatch.setattr(bt, "_run_segment", _run_segment_ordered)

    df = pd.read_csv("tests/fixtures/sample_ohlcv.csv")
    result = bt.backtest_strategy(df=df, pair="EUR_USD", strategy_module=_DummyStrategy(), min_trades=30)

    assert result["overfit_warning"] is False
    assert result["overfit_reason"] == "insufficient_trades"


def test_overfit_enabled_when_gap_exceeds_threshold_with_sufficient_trades(monkeypatch) -> None:
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        return df

    calls = {"n": 0}

    def _run_segment_ordered(*args, **kwargs) -> pd.DataFrame:
        calls["n"] += 1
        if calls["n"] == 1:
            return pd.DataFrame({"pnl_pips": [1.0] * 40 + [-1.0] * 10})  # 0.80 win rate
        return pd.DataFrame({"pnl_pips": [1.0] * 20 + [-1.0] * 30})  # 0.40 win rate

    monkeypatch.setattr(bt, "_prepare_indicators", _prepare)
    monkeypatch.setattr(bt, "_run_segment", _run_segment_ordered)

    df = pd.read_csv("tests/fixtures/sample_ohlcv.csv")
    result = bt.backtest_strategy(df=df, pair="EUR_USD", strategy_module=_DummyStrategy(), min_trades=30)

    assert result["gap"] > 0.15
    assert result["overfit_warning"] is True
    assert result["overfit_reason"] == "gap_exceeds_threshold"
