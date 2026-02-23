from __future__ import annotations

from api.strategy_params_validation import validate_params


def test_validate_params_rejects_unknown_and_out_of_range() -> None:
    errors = validate_params(
        "vwap_rsi",
        {
            "rsi_buy_max": -1,
            "rsi_sell_min": 101,
            "vwap_atr_tolerance": 1.1,
            "rsi_period": 0,
            "extra": 1,
        },
    )
    fields = {item["field"] for item in errors}
    assert "extra" in fields
    assert "rsi_buy_max" in fields
    assert "rsi_sell_min" in fields
    assert "vwap_atr_tolerance" in fields
    assert "rsi_period" in fields


def test_validate_params_accepts_boundaries() -> None:
    errors = validate_params(
        "vwap_rsi",
        {
            "rsi_buy_max": 0,
            "rsi_sell_min": 100,
            "vwap_atr_tolerance": 1,
            "rsi_period": 1,
        },
    )
    assert errors == []
