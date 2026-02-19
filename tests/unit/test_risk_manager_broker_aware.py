import pytest
from execution import risk_manager


def test_pip_size_from_location() -> None:
    assert risk_manager.pip_size_from_location(-4) == 0.0001
    assert risk_manager.pip_size_from_location(-2) == 0.01


def test_calculate_sl_tp_buy_sell() -> None:
    buy_sl, buy_tp = risk_manager.calculate_sl_tp(entry=1.2, direction="BUY", atr_val=0.001)
    sell_sl, sell_tp = risk_manager.calculate_sl_tp(entry=1.2, direction="SELL", atr_val=0.001)

    assert buy_sl == pytest.approx(1.1985)
    assert buy_tp == pytest.approx(1.203)
    assert sell_sl == pytest.approx(1.2015)
    assert sell_tp == pytest.approx(1.197)


def test_calculate_position_size_with_broker_specs(monkeypatch) -> None:
    monkeypatch.setattr(
        risk_manager,
        "get_instrument_specs",
        lambda *args, **kwargs: {
            "pip_location": -4,
            "min_units": 1000,
            "trade_units_precision": 0,
        },
    )

    units = risk_manager.calculate_position_size(
        pair="EUR_USD",
        entry=1.2000,
        sl_price=1.1990,
        balance=10_000,
        client=object(),
        account_id="acct",
        risk_per_trade=0.01,
    )

    assert units == 100000
