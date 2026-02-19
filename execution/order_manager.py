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


def count_open_positions(client, account_id: str) -> tuple[int, dict[str, int]]:
    """Return total count of open instruments and per-pair net unit map.

    Fails closed by returning an impossible high count and empty map on API errors.
    """
    try:
        from oandapyV20.endpoints import positions

        request = positions.OpenPositions(account_id)
        client.request(request)
        positions_data = request.response.get("positions", [])

        per_pair: dict[str, int] = {}
        total_open = 0
        for pos in positions_data:
            pair = pos.get("instrument")
            long_units = int(pos.get("long", {}).get("units", 0))
            short_units = int(pos.get("short", {}).get("units", 0))
            net_units = long_units - abs(short_units)
            if net_units != 0 and pair:
                per_pair[pair] = net_units
                total_open += 1

        return total_open, per_pair
    except Exception:
        return 99_999, {}


def can_open_new_position(pair: str, client, account_id: str, max_total: int = 3) -> bool:
    """Return True when pair is not already open and total open is under max."""
    try:
        if has_open_position(pair, client, account_id):
            return False
        total_open, _ = count_open_positions(client, account_id)
        return total_open < max_total
    except Exception:
        return False


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
