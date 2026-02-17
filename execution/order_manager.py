"""Order execution and position state helpers."""

from __future__ import annotations


def place_market_order() -> None:
    """Place a market order (not implemented in this phase)."""
    raise NotImplementedError("place_market_order is not implemented yet.")


def has_open_position(pair: str, client, account_id: str) -> bool:
    """Return True when an instrument already has an open position.

    This is a minimal live-safe gate helper for Phase 4.
    On any API error, returns True (fail-closed) to avoid accidental double exposure.
    """
    try:
        from oandapyV20.endpoints.positions import OpenPositions

        endpoint = OpenPositions(accountID=account_id)
        response = client.request(endpoint)
        positions = response.get("positions", [])

        for position in positions:
            if position.get("instrument") != pair:
                continue
            long_units = float(position.get("long", {}).get("units", 0.0))
            short_units = float(position.get("short", {}).get("units", 0.0))
            if long_units != 0.0 or short_units != 0.0:
                return True
        return False
    except Exception:
        return True
