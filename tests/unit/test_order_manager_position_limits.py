from __future__ import annotations

import sys
import types

from execution import order_manager


class FakeClient:
    def request(self, request_obj):
        return request_obj.response


def _install_fake_open_positions(monkeypatch, open_positions: list[dict], position_details: dict) -> None:
    positions_mod = types.ModuleType("positions")

    class OpenPositions:
        def __init__(self, account_id):
            self.account_id = account_id
            self.response = {"positions": open_positions}

    class PositionDetails:
        def __init__(self, account_id, instrument):
            self.account_id = account_id
            self.instrument = instrument
            self.response = {"position": position_details.get(instrument, {})}

    positions_mod.OpenPositions = OpenPositions
    positions_mod.PositionDetails = PositionDetails

    endpoints_mod = types.ModuleType("endpoints")
    endpoints_mod.positions = positions_mod

    root_mod = types.ModuleType("oandapyV20")
    root_mod.endpoints = endpoints_mod

    monkeypatch.setitem(sys.modules, "oandapyV20", root_mod)
    monkeypatch.setitem(sys.modules, "oandapyV20.endpoints", endpoints_mod)
    monkeypatch.setitem(sys.modules, "oandapyV20.endpoints.positions", positions_mod)


def test_count_open_positions_returns_total_and_map(monkeypatch) -> None:
    _install_fake_open_positions(
        monkeypatch,
        open_positions=[
            {"instrument": "EUR_USD", "long": {"units": "100"}, "short": {"units": "0"}},
            {"instrument": "USD_JPY", "long": {"units": "0"}, "short": {"units": "50"}},
            {"instrument": "GBP_USD", "long": {"units": "0"}, "short": {"units": "0"}},
        ],
        position_details={"EUR_USD": {"long": {"units": "0"}, "short": {"units": "0"}}},
    )

    total, per_pair = order_manager.count_open_positions(FakeClient(), "acct")

    assert total == 2
    assert per_pair == {"EUR_USD": 100, "USD_JPY": -50}


def test_can_open_new_position_respects_pair_and_total(monkeypatch) -> None:
    _install_fake_open_positions(
        monkeypatch,
        open_positions=[
            {"instrument": "EUR_USD", "long": {"units": "100"}, "short": {"units": "0"}},
            {"instrument": "USD_JPY", "long": {"units": "10"}, "short": {"units": "0"}},
        ],
        position_details={
            "EUR_USD": {"long": {"units": "100"}, "short": {"units": "0"}},
            "AUD_USD": {"long": {"units": "0"}, "short": {"units": "0"}},
        },
    )

    assert order_manager.can_open_new_position("EUR_USD", FakeClient(), "acct", max_total=3) is False
    assert order_manager.can_open_new_position("AUD_USD", FakeClient(), "acct", max_total=2) is False
    assert order_manager.can_open_new_position("AUD_USD", FakeClient(), "acct", max_total=3) is True
