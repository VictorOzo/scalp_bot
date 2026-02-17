from __future__ import annotations

from execution.risk_manager import compute_sl_tp_prices, pip_size, round_price


def test_pip_size() -> None:
    assert pip_size("USD_JPY") == 0.01
    assert pip_size("EUR_USD") == 0.0001


def test_round_price() -> None:
    assert round_price("USD_JPY", 150.1239) == 150.124
    assert round_price("EUR_USD", 1.1234567) == 1.12346


def test_compute_sl_tp_prices_buy() -> None:
    sl, tp = compute_sl_tp_prices(
        pair="EUR_USD",
        direction="BUY",
        entry_price=1.10000,
        atr=0.0010,
        sl_atr_mult=1.5,
        tp_atr_mult=2.0,
    )
    assert sl == 1.0985
    assert tp == 1.102


def test_compute_sl_tp_prices_sell_jpy_rounding() -> None:
    sl, tp = compute_sl_tp_prices(
        pair="USD_JPY",
        direction="SELL",
        entry_price=150.000,
        atr=0.1234,
        sl_atr_mult=1.5,
        tp_atr_mult=2.0,
    )
    assert sl == 150.185
    assert tp == 149.753
