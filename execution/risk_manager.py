"""Risk management and protective-level helpers."""

from __future__ import annotations

from datetime import datetime, timezone

_START_OF_DAY_NAV: dict[str, float] = {}


def pip_size(pair: str) -> float:
    """Return instrument pip size (JPY pairs use 0.01, others 0.0001)."""
    return 0.01 if pair.endswith("JPY") else 0.0001


def round_price(pair: str, price: float) -> float:
    """Round price to broker-friendly precision (JPY=3 decimals, others=5)."""
    return round(price, 3 if pair.endswith("JPY") else 5)


def compute_sl_tp_prices(
    pair: str,
    direction: str,
    entry_price: float,
    atr: float,
    sl_atr_mult: float = 1.5,
    tp_atr_mult: float = 2.0,
) -> tuple[float, float]:
    """Compute rounded SL/TP prices from ATR multiples."""
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if atr <= 0:
        raise ValueError("atr must be positive")

    if direction == "BUY":
        sl = entry_price - sl_atr_mult * atr
        tp = entry_price + tp_atr_mult * atr
    else:
        sl = entry_price + sl_atr_mult * atr
        tp = entry_price - tp_atr_mult * atr

    return round_price(pair, sl), round_price(pair, tp)


def compute_units_fixed_risk(
    balance: float,
    risk_pct: float,
    pair: str,
    sl_distance_price: float,
    pip_value_per_unit: float | None = None,
) -> int:
    """Return approximate units for a fixed-risk position size.

    This is intentionally simple sizing for paper-trading: when per-unit pip value
    is unknown, it uses a rough default estimate and does not attempt full FX
    conversion accuracy.
    """
    if balance <= 0 or risk_pct <= 0 or sl_distance_price <= 0:
        return 1

    risk_amount = balance * risk_pct
    distance_pips = sl_distance_price / pip_size(pair)
    value_per_unit_per_pip = pip_value_per_unit if pip_value_per_unit is not None else 0.0001

    if distance_pips <= 0 or value_per_unit_per_pip <= 0:
        return 1

    units = risk_amount / (distance_pips * value_per_unit_per_pip)
    return max(1, int(units))


def is_within_daily_limit(client, account_id: str, daily_max_loss: float = 0.03) -> bool:
    """Return False once current NAV drawdown exceeds the daily cap.

    Minimal placeholder: stores UTC-date-keyed start-of-day NAV in-memory and compares
    current NAV against it. This is intentionally simple until full realized/unrealized
    PnL tracking is implemented.

    On API errors, this function fails closed and returns False.
    """
    try:
        from oandapyV20.endpoints.accounts import AccountSummary

        today = datetime.now(timezone.utc).date().isoformat()
        endpoint = AccountSummary(accountID=account_id)
        response = client.request(endpoint)
        nav = float(response["account"]["NAV"])

        if today not in _START_OF_DAY_NAV:
            _START_OF_DAY_NAV.clear()
            _START_OF_DAY_NAV[today] = nav

        start_nav = _START_OF_DAY_NAV[today]
        if start_nav <= 0:
            return False

        drawdown = (start_nav - nav) / start_nav
        return drawdown < daily_max_loss
    except Exception:
        return False
