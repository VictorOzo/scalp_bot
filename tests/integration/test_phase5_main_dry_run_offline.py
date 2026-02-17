from __future__ import annotations

import io
import logging

import main


def test_phase5_execute_cycle_dry_run_offline(monkeypatch, sample_ohlcv_df, capsys) -> None:
    class FakeClient:
        pass

    fake_client = FakeClient()
    logger = logging.getLogger("phase5_test")
    logger.handlers = [logging.StreamHandler(io.StringIO())]

    monkeypatch.setattr(main, "DRY_RUN", True)
    monkeypatch.setattr(main, "has_open_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(main, "get_live_bid_ask", lambda pair, client, aid: (1.1000, 1.1002))
    monkeypatch.setattr(main, "get_candles", lambda *args, **kwargs: sample_ohlcv_df.copy())
    monkeypatch.setattr(main, "calculate_atr", lambda df: df.assign(atr=0.0012))
    monkeypatch.setattr(main, "_get_account_balance", lambda *args, **kwargs: 10000.0)

    def _never_call(*args, **kwargs):
        raise AssertionError("place_market_order should not be called in DRY_RUN")

    monkeypatch.setattr(main, "place_market_order", _never_call)

    monkeypatch.setattr(
        main,
        "STRATEGY_FN",
        {
            "ema_vwap": lambda c, a: "BUY",
            "bb_breakout": lambda c, a: "HOLD",
            "vwap_rsi": lambda c, a: "HOLD",
        },
    )

    main.execute_cycle(fake_client, "acct", logger)
    out = capsys.readouterr().out
    assert "DRY_RUN EUR_USD BUY" in out
