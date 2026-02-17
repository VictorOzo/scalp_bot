"""Spread-based trade gating utilities."""

from __future__ import annotations

MAX_SPREAD_PIPS: dict[str, float] = {
    "EUR_USD": 1.5,
    "GBP_USD": 2.5,
    "USD_JPY": 2.0,
}


def _pip_size(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


def calculate_spread_pips(pair: str, bid: float, ask: float) -> float:
    """Return spread in pips for the instrument."""
    if bid <= 0 or ask <= 0:
        raise ValueError("bid and ask must be positive")
    if ask <= bid:
        raise ValueError("ask must be greater than bid")

    return (ask - bid) / _pip_size(pair)


def is_spread_acceptable(
    pair: str,
    bid: float,
    ask: float,
    max_spread_override: float | None = None,
) -> bool:
    """Return True when spread is below configured or overridden maximum."""
    max_spread = max_spread_override if max_spread_override is not None else MAX_SPREAD_PIPS.get(pair)
    if max_spread is None:
        return False

    spread_pips = calculate_spread_pips(pair=pair, bid=bid, ask=ask)
    return spread_pips <= max_spread


def get_live_bid_ask(pair: str, client, account_id: str) -> tuple[float, float]:
    """Fetch best bid/ask from OANDA pricing endpoint."""
    from oandapyV20.endpoints.pricing import PricingInfo

    endpoint = PricingInfo(accountID=account_id, params={"instruments": pair})
    response = client.request(endpoint)

    prices = response.get("prices", [])
    if not prices:
        raise ValueError("No pricing data returned from OANDA")

    price = prices[0]
    bids = price.get("bids", [])
    asks = price.get("asks", [])
    if not bids or not asks:
        raise ValueError("Pricing payload missing bids/asks")

    bid = float(bids[0]["price"])
    ask = float(asks[0]["price"])
    return bid, ask


def is_spread_acceptable_live(pair: str, client, account_id: str) -> bool:
    """Return spread gate decision using live OANDA pricing."""
    bid, ask = get_live_bid_ask(pair=pair, client=client, account_id=account_id)
    return is_spread_acceptable(pair=pair, bid=bid, ask=ask)
