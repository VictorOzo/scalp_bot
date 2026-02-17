"""Order execution and position reconciliation helpers."""

from __future__ import annotations


def has_open_position(pair: str, client, account_id: str) -> bool:
    """Return True when the account already has non-zero units for the instrument.

    This reconciliation check is intentionally fail-closed: API failures return True
    so the engine avoids accidental double exposure after restarts.
    """
    try:
        from oandapyV20.endpoints import positions

        request = positions.PositionDetails(account_id, instrument=pair)
        client.request(request)
        pos = request.response.get("position", {})
        long_units = int(pos.get("long", {}).get("units", 0))
        short_units = int(pos.get("short", {}).get("units", 0))
        return abs(long_units) > 0 or abs(short_units) > 0
    except Exception:
        return True


def get_open_units(pair: str, client, account_id: str) -> int:
    """Return signed net open units for the pair (long - short).

    On API errors returns 0 for logging convenience.
    """
    try:
        from oandapyV20.endpoints import positions

        request = positions.PositionDetails(account_id, instrument=pair)
        client.request(request)
        pos = request.response.get("position", {})
        long_units = int(pos.get("long", {}).get("units", 0))
        short_units = int(pos.get("short", {}).get("units", 0))
        return long_units - abs(short_units)
    except Exception:
        return 0


def place_market_order(
    pair: str,
    direction: str,
    units: int,
    sl_price: float,
    tp_price: float,
    client,
    account_id: str,
) -> dict:
    """Submit a market order with SL/TP attached in the same OrderCreate request."""
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if units <= 0:
        raise ValueError("units must be positive")

    from oandapyV20.endpoints import orders

    signed = units if direction == "BUY" else -units
    data = {
        "order": {
            "type": "MARKET",
            "instrument": pair,
            "units": str(signed),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": str(round(sl_price, 5))},
            "takeProfitOnFill": {"price": str(round(tp_price, 5))},
        }
    }

    request = orders.OrderCreate(account_id, data=data)
    client.request(request)
    return request.response
