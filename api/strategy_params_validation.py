from __future__ import annotations

from typing import Any

from storage.strategy_params import DEFAULT_PRESETS, PROFILES


RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "ema_vwap": {
        "vwap_atr_tolerance": (0.0, 1.0),
    },
    "vwap_rsi": {
        "rsi_buy_max": (0.0, 100.0),
        "rsi_sell_min": (0.0, 100.0),
        "vwap_atr_tolerance": (0.0, 1.0),
        "rsi_period": (1.0, 100.0),
    },
    "bb_breakout": {
        "volume_spike_mult": (0.0, 5.0),
        "squeeze_percentile": (0.0, 100.0),
        "squeeze_expand_mult": (0.5, 3.0),
    },
}


def validate_strategy_and_profile(strategy_name: str, profile: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if strategy_name not in DEFAULT_PRESETS:
        errors.append({"field": "strategy_name", "message": f"Unknown strategy '{strategy_name}'"})
    if profile not in PROFILES:
        errors.append({"field": "profile", "message": f"Unknown profile '{profile}'"})
    return errors


def validate_params(strategy_name: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    schema = RANGES.get(strategy_name)
    if schema is None:
        return [{"field": "strategy_name", "message": f"Unknown strategy '{strategy_name}'"}]

    errors: list[dict[str, str]] = []

    for key in payload.keys():
        if key not in schema:
            errors.append({"field": key, "message": "Unknown parameter key"})

    for required_key in schema.keys():
        if required_key not in payload:
            errors.append({"field": required_key, "message": "Missing required parameter"})

    for key, (lower, upper) in schema.items():
        if key not in payload:
            continue

        value = payload[key]
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors.append({"field": key, "message": "Must be a number"})
            continue

        if number < lower or number > upper:
            errors.append({"field": key, "message": f"Must be between {lower} and {upper}"})

    if strategy_name == "vwap_rsi":
        buy = payload.get("rsi_buy_max")
        sell = payload.get("rsi_sell_min")
        if buy is not None and sell is not None:
            try:
                if float(buy) >= float(sell):
                    errors.append({"field": "rsi_buy_max", "message": "Must be less than rsi_sell_min"})
            except (TypeError, ValueError):
                pass

    return errors
