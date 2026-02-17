from __future__ import annotations

import importlib
from typing import Any

import pandas as pd
import pytest

STRATEGY_MODULES = [
    "strategies.ema_vwap",
    "strategies.bb_breakout",
    "strategies.vwap_rsi",
]


def _base_df(rows: int = 160) -> pd.DataFrame:
    times = pd.date_range("2024-01-01", periods=rows, freq="5min", tz="UTC")
    close = pd.Series([1.0 + i * 0.0001 for i in range(rows)])
    return pd.DataFrame(
        {
            "time": times,
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "volume": [100] * rows,
        }
    )


@pytest.mark.parametrize("module_name", STRATEGY_MODULES)
def test_gate_order_stops_immediately_on_session_block(monkeypatch: pytest.MonkeyPatch, module_name: str) -> None:
    mod = importlib.import_module(module_name)
    calls: dict[str, int] = {
        "spread": 0,
        "news": 0,
        "open_pos": 0,
        "daily": 0,
        "candles": 0,
    }

    monkeypatch.setattr(mod, "is_session_active", lambda pair: False)
    monkeypatch.setattr(mod, "is_spread_acceptable_live", lambda *args, **kwargs: calls.__setitem__("spread", calls["spread"] + 1) or True)
    monkeypatch.setattr(mod, "is_news_clear", lambda *args, **kwargs: calls.__setitem__("news", calls["news"] + 1) or True)
    monkeypatch.setattr(mod, "has_open_position", lambda *args, **kwargs: calls.__setitem__("open_pos", calls["open_pos"] + 1) or False)
    monkeypatch.setattr(mod, "is_within_daily_limit", lambda *args, **kwargs: calls.__setitem__("daily", calls["daily"] + 1) or True)
    monkeypatch.setattr(mod, "get_candles", lambda *args, **kwargs: calls.__setitem__("candles", calls["candles"] + 1) or _base_df())

    assert mod.get_signal(client=object(), account_id="id") == "HOLD"
    assert calls == {"spread": 0, "news": 0, "open_pos": 0, "daily": 0, "candles": 0}


@pytest.mark.parametrize("module_name", STRATEGY_MODULES)
def test_gate_order_reaches_only_until_first_block(monkeypatch: pytest.MonkeyPatch, module_name: str) -> None:
    mod = importlib.import_module(module_name)
    calls: dict[str, int] = {"spread": 0, "news": 0, "open_pos": 0, "daily": 0}

    monkeypatch.setattr(mod, "is_session_active", lambda pair: True)
    monkeypatch.setattr(mod, "is_spread_acceptable_live", lambda *args, **kwargs: calls.__setitem__("spread", calls["spread"] + 1) or True)
    monkeypatch.setattr(mod, "is_news_clear", lambda *args, **kwargs: calls.__setitem__("news", calls["news"] + 1) or False)
    monkeypatch.setattr(mod, "has_open_position", lambda *args, **kwargs: calls.__setitem__("open_pos", calls["open_pos"] + 1) or False)
    monkeypatch.setattr(mod, "is_within_daily_limit", lambda *args, **kwargs: calls.__setitem__("daily", calls["daily"] + 1) or True)

    assert mod.get_signal(client=object(), account_id="id") == "HOLD"
    assert calls["spread"] == 1
    assert calls["news"] == 1
    assert calls["open_pos"] == 0
    assert calls["daily"] == 0


def test_ema_vwap_buy_and_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("strategies.ema_vwap")
    monkeypatch.setattr(mod, "is_session_active", lambda pair: True)
    monkeypatch.setattr(mod, "is_spread_acceptable_live", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_news_clear", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "has_open_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(mod, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_strategy_allowed", lambda *args, **kwargs: True)

    buy_df = _base_df()
    sell_df = _base_df()

    monkeypatch.setattr(mod, "get_candles", lambda *args, **kwargs: _base_df())
    monkeypatch.setattr(mod, "calculate_atr", lambda df: df.assign(atr=0.001))
    monkeypatch.setattr(mod, "calculate_adx", lambda df: df.assign(adx=30.0))

    monkeypatch.setattr(
        mod,
        "calculate_ema",
        lambda df, *args, **kwargs: buy_df.assign(
            cross_up=lambda x: x.index == x.index[-1],
            cross_down=False,
        ),
    )
    monkeypatch.setattr(mod, "calculate_vwap", lambda df: df.assign(vwap=df["close"] - 0.0005))
    assert mod.get_signal(client=object(), account_id="id") == "BUY"

    monkeypatch.setattr(
        mod,
        "calculate_ema",
        lambda df, *args, **kwargs: sell_df.assign(
            cross_up=False,
            cross_down=lambda x: x.index == x.index[-1],
        ),
    )
    monkeypatch.setattr(mod, "calculate_vwap", lambda df: df.assign(vwap=df["close"] + 0.0005))
    assert mod.get_signal(client=object(), account_id="id") == "SELL"



def test_bb_breakout_buy_and_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("strategies.bb_breakout")
    monkeypatch.setattr(mod, "is_session_active", lambda pair: True)
    monkeypatch.setattr(mod, "is_spread_acceptable_live", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_news_clear", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "has_open_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(mod, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_strategy_allowed", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "get_candles", lambda *args, **kwargs: _base_df())
    monkeypatch.setattr(mod, "calculate_atr", lambda df: df.assign(atr=0.001))
    monkeypatch.setattr(mod, "calculate_adx", lambda df: df.assign(adx=22.0))

    def _bb_buy(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
        out = df.copy()
        out["bb_upper"] = out["close"] - 0.0003
        out["bb_lower"] = out["close"] - 0.0008
        out["bb_width"] = 0.01
        out.loc[out.index[-2], "bb_width"] = 0.005
        out.loc[out.index[-1], "bb_width"] = 0.008
        out.loc[out.index[-1], "volume"] = 1000
        return out

    monkeypatch.setattr(mod, "calculate_bollinger", _bb_buy)
    assert mod.get_signal(client=object(), account_id="id") == "BUY"

    def _bb_sell(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
        out = df.copy()
        out["bb_upper"] = out["close"] + 0.0008
        out["bb_lower"] = out["close"] + 0.0003
        out["bb_width"] = 0.01
        out.loc[out.index[-2], "bb_width"] = 0.005
        out.loc[out.index[-1], "bb_width"] = 0.008
        out.loc[out.index[-1], "volume"] = 1000
        return out

    monkeypatch.setattr(mod, "calculate_bollinger", _bb_sell)
    assert mod.get_signal(client=object(), account_id="id") == "SELL"


def test_vwap_rsi_buy_and_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("strategies.vwap_rsi")
    monkeypatch.setattr(mod, "is_session_active", lambda pair: True)
    monkeypatch.setattr(mod, "is_spread_acceptable_live", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_news_clear", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "has_open_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(mod, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "is_strategy_allowed", lambda *args, **kwargs: True)
    monkeypatch.setattr(mod, "get_candles", lambda *args, **kwargs: _base_df())
    monkeypatch.setattr(mod, "calculate_atr", lambda df: df.assign(atr=0.001))
    monkeypatch.setattr(mod, "calculate_adx", lambda df: df.assign(adx=18.0))

    monkeypatch.setattr(mod, "calculate_rsi", lambda df, period=3: df.assign(rsi=10.0))
    monkeypatch.setattr(mod, "calculate_vwap", lambda df: df.assign(vwap=df["close"] - 0.0003))
    assert mod.get_signal(client=object(), account_id="id") == "BUY"

    monkeypatch.setattr(mod, "calculate_rsi", lambda df, period=3: df.assign(rsi=90.0))
    monkeypatch.setattr(mod, "calculate_vwap", lambda df: df.assign(vwap=df["close"] + 0.0003))
    assert mod.get_signal(client=object(), account_id="id") == "SELL"


@pytest.mark.parametrize("module_name", STRATEGY_MODULES)
def test_signal_return_domain(monkeypatch: pytest.MonkeyPatch, module_name: str) -> None:
    mod = importlib.import_module(module_name)
    monkeypatch.setattr(mod, "is_session_active", lambda pair: False)
    out = mod.get_signal(client=object(), account_id="id")
    assert out in {"BUY", "SELL", "HOLD"}
