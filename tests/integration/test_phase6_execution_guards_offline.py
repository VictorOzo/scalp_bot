from __future__ import annotations

import io
import logging

import main


def _logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers = [logging.StreamHandler(io.StringIO())]
    logger.setLevel(logging.INFO)
    return logger


def test_phase6_guards_block_order_placement(monkeypatch, sample_ohlcv_df) -> None:
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "can_open_new_position", lambda *args, **kwargs: False)
    monkeypatch.setattr(main, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "get_live_bid_ask", lambda *args, **kwargs: (1.1, 1.1002))
    monkeypatch.setattr(main, "get_candles", lambda *args, **kwargs: sample_ohlcv_df.copy())
    monkeypatch.setattr(main, "calculate_atr", lambda df: df.assign(atr=0.001))
    monkeypatch.setattr(main, "get_instrument_specs", lambda *args, **kwargs: {"min_units": 111})

    called = {"order": 0}

    def _order(*args, **kwargs):
        called["order"] += 1
        return {"ok": True}

    monkeypatch.setattr(main, "place_market_order", _order)
    monkeypatch.setattr(
        main,
        "STRATEGY_FN",
        {
            "ema_vwap": lambda c, a: "BUY",
            "bb_breakout": lambda c, a: "HOLD",
            "vwap_rsi": lambda c, a: "HOLD",
        },
    )

    main.execute_cycle(client=object(), account_id="acct", logger=_logger("phase6_block"))
    assert called["order"] == 0


def test_phase6_dry_run_prints_intended_order(monkeypatch, sample_ohlcv_df, capsys) -> None:
    monkeypatch.setattr(main, "DRY_RUN", True)
    monkeypatch.setattr(main, "can_open_new_position", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "is_within_daily_limit", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "get_live_bid_ask", lambda *args, **kwargs: (1.1, 1.1002))
    monkeypatch.setattr(main, "get_candles", lambda *args, **kwargs: sample_ohlcv_df.copy())
    monkeypatch.setattr(main, "calculate_atr", lambda df: df.assign(atr=0.001))
    monkeypatch.setattr(main, "get_instrument_specs", lambda *args, **kwargs: {"min_units": 321})

    def _never_call(*args, **kwargs):
        raise AssertionError("place_market_order should not be called during DRY_RUN")

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

    main.execute_cycle(client=object(), account_id="acct", logger=_logger("phase6_dry"))
    out = capsys.readouterr().out
    assert "DRY_RUN EUR_USD BUY units=321" in out
    assert "sl=1.0987" in out
    assert "tp=1.1032" in out
