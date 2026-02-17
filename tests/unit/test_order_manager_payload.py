from __future__ import annotations

import sys
import types

from execution import order_manager


class FakeClient:
    def __init__(self) -> None:
        self.requests = []

    def request(self, request_obj):
        self.requests.append(request_obj)
        if not hasattr(request_obj, "response"):
            request_obj.response = {"ok": True}
        return request_obj.response


def _install_fake_oanda(monkeypatch, position_response: dict) -> None:
    positions_mod = types.ModuleType("positions")
    orders_mod = types.ModuleType("orders")

    class PositionDetails:
        def __init__(self, account_id, instrument):
            self.account_id = account_id
            self.instrument = instrument
            self.response = {"position": position_response}

    class OrderCreate:
        def __init__(self, account_id, data):
            self.account_id = account_id
            self.data = data
            self.response = {"orderCreateTransaction": {"id": "abc123"}}

    positions_mod.PositionDetails = PositionDetails
    orders_mod.OrderCreate = OrderCreate

    endpoints_mod = types.ModuleType("endpoints")
    endpoints_mod.positions = positions_mod
    endpoints_mod.orders = orders_mod

    root_mod = types.ModuleType("oandapyV20")
    root_mod.endpoints = endpoints_mod

    monkeypatch.setitem(sys.modules, "oandapyV20", root_mod)
    monkeypatch.setitem(sys.modules, "oandapyV20.endpoints", endpoints_mod)
    monkeypatch.setitem(sys.modules, "oandapyV20.endpoints.positions", positions_mod)
    monkeypatch.setitem(sys.modules, "oandapyV20.endpoints.orders", orders_mod)


def test_has_open_position_true_when_units_non_zero(monkeypatch) -> None:
    _install_fake_oanda(monkeypatch, {"long": {"units": "100"}, "short": {"units": "0"}})
    assert order_manager.has_open_position("EUR_USD", FakeClient(), "acct") is True


def test_has_open_position_false_when_zero_units(monkeypatch) -> None:
    _install_fake_oanda(monkeypatch, {"long": {"units": "0"}, "short": {"units": "0"}})
    assert order_manager.has_open_position("EUR_USD", FakeClient(), "acct") is False


def test_place_market_order_payload_buy_contains_sltp(monkeypatch) -> None:
    _install_fake_oanda(monkeypatch, {"long": {"units": "0"}, "short": {"units": "0"}})
    client = FakeClient()

    out = order_manager.place_market_order(
        pair="EUR_USD",
        direction="BUY",
        units=1200,
        sl_price=1.10123,
        tp_price=1.10987,
        client=client,
        account_id="acct",
    )

    assert out["orderCreateTransaction"]["id"] == "abc123"
    payload = client.requests[-1].data["order"]
    assert payload["units"] == "1200"
    assert payload["stopLossOnFill"]["price"] == "1.10123"
    assert payload["takeProfitOnFill"]["price"] == "1.10987"


def test_place_market_order_payload_sell_signed_units(monkeypatch) -> None:
    _install_fake_oanda(monkeypatch, {"long": {"units": "0"}, "short": {"units": "0"}})
    client = FakeClient()

    order_manager.place_market_order(
        pair="GBP_USD",
        direction="SELL",
        units=500,
        sl_price=1.25001,
        tp_price=1.24001,
        client=client,
        account_id="acct",
    )

    payload = client.requests[-1].data["order"]
    assert payload["units"] == "-500"
    assert "stopLossOnFill" in payload
    assert "takeProfitOnFill" in payload
