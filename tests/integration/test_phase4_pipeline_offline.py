from __future__ import annotations

import os

import pytest

from config.settings import OANDA_ACCOUNT_ID, OANDA_API_KEY
from data.fetcher import get_candles, get_oanda_client
from strategies import bb_breakout, ema_vwap, vwap_rsi


@pytest.mark.parametrize(
    "pair,module,strategy_name",
    [
        ("EUR_USD", ema_vwap, "ema_vwap"),
        ("GBP_USD", bb_breakout, "bb_breakout"),
        ("USD_JPY", vwap_rsi, "vwap_rsi"),
    ],
)
def test_phase4_pipeline_offline_all_gates_pass(
    monkeypatch: pytest.MonkeyPatch,
    sample_ohlcv_df,
    pair,
    module,
    strategy_name,
) -> None:
    monkeypatch.setattr(module, "get_candles", lambda *args, **kwargs: sample_ohlcv_df.copy())
    monkeypatch.setattr(module, "is_session_active", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "is_spread_acceptable_live", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "is_news_clear", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "has_open_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "is_strategy_allowed", lambda *args, **kwargs: True)

    signal = module.get_signal(client=object(), account_id="offline")
    assert signal in {"BUY", "SELL", "HOLD"}

    if os.getenv("DEBUG_PHASE4") == "1":
        df = sample_ohlcv_df.copy()
        df = module.calculate_atr(df)
        df = module.calculate_adx(df)
        if strategy_name == "ema_vwap":
            df = module.calculate_ema(df)
            df = module.calculate_vwap(df)
        elif strategy_name == "bb_breakout":
            df = module.calculate_bollinger(df)
            df = df.assign(rsi=float("nan"), vwap=float("nan"))
        else:
            df = module.calculate_rsi(df)
            df = module.calculate_vwap(df)
        last = df.iloc[-1]
        print(
            f"{pair} {strategy_name} -> {signal} | "
            f"adx={last.get('adx')} atr={last.get('atr')} vwap={last.get('vwap')} rsi={last.get('rsi')}"
        )


@pytest.mark.live
@pytest.mark.skipif(not (OANDA_API_KEY and OANDA_ACCOUNT_ID), reason="OANDA credentials not set")
def test_phase4_live_smoke_optional() -> None:
    client = get_oanda_client()
    account_id = OANDA_ACCOUNT_ID

    for strategy in (ema_vwap, bb_breakout, vwap_rsi):
        signal = strategy.get_signal(client, account_id)
        assert signal in {"BUY", "SELL", "HOLD"}


@pytest.mark.live
def test_live_marker_documented_only() -> None:
    """Placeholder to keep the optional live marker visible in collection."""
    assert True
