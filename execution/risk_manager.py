"""Risk management and protective-level helpers."""

from __future__ import annotations

from datetime import datetime, timezone

RISK_PER_TRADE = 0.01
MAX_DAILY_LOSS = 0.03
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.0
MAX_OPEN_POSITIONS_TOTAL = 3

_START_OF_DAY_NAV: dict[str, float] = {}
_INSTRUMENT_SPECS_CACHE: dict[str, tuple[float, dict[str, int]]] = {}


def _fallback_specs(pair: str) -> dict[str, int]:
    return {
        "pip_location": -2 if pair.endswith("JPY") else -4,
        "min_units": 1,
        "trade_units_precision": 0,
    }


def get_instrument_specs(pair: str, client, account_id: str, ttl_s: int = 3600) -> dict[str, int]:
    """Return instrument pip/trade sizing specs from OANDA with TTL caching."""
    now = datetime.now(timezone.utc).timestamp()
    cached = _INSTRUMENT_SPECS_CACHE.get(pair)
    if cached is not None:
        cached_ts, cached_specs = cached
        if now - cached_ts <= ttl_s:
            return cached_specs

    try:
        from oandapyV20.endpoints.accounts import AccountInstruments

        request = AccountInstruments(account_id, params={"instruments": pair})
        client.request(request)
        instrument = request.response["instruments"][0]
        specs = {
            "pip_location": int(instrument["pipLocation"]),
            "min_units": int(instrument.get("minimumTradeSize", 1)),
            "trade_units_precision": int(instrument.get("tradeUnitsPrecision", 0)),
        }
    except Exception:
        specs = _fallback_specs(pair)

    _INSTRUMENT_SPECS_CACHE[pair] = (now, specs)
    return specs


def pip_size_from_location(pip_location: int) -> float:
    return 10**pip_location


def calculate_sl_tp(entry: float, direction: str, atr_val: float) -> tuple[float, float]:
    """Calculate SL/TP from entry + ATR using fixed RR 1:2 off SL distance."""
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if atr_val <= 0:
        raise ValueError("atr_val must be positive")

    sl_dist = atr_val * SL_ATR_MULT
    tp_dist = sl_dist * TP_ATR_MULT
    if direction == "BUY":
        return entry - sl_dist, entry + tp_dist
    return entry + sl_dist, entry - tp_dist


def quantize_units(units: float, trade_units_precision: int) -> int:
    """Quantize units before int-cast.

    OANDA accepts integer units. We keep this intentionally simple: when
    precision > 0 we round to that precision first, then cast to int.
    """
    if trade_units_precision <= 0:
        return int(units)
    return int(round(units, trade_units_precision))


def calculate_position_size(
    pair: str,
    entry: float,
    sl_price: float,
    balance: float,
    client,
    account_id: str,
    risk_per_trade: float = RISK_PER_TRADE,
) -> int:
    """Compute simple broker-aware size from SL distance and instrument specs.

    Limitation: this keeps the Phase 6 simplified model and does not apply
    quote/base currency conversion adjustments for true pip value per unit.
    """
    specs = get_instrument_specs(pair, client, account_id)
    min_units = int(specs.get("min_units", 1))

    try:
        pip_size = pip_size_from_location(int(specs["pip_location"]))
        risk_amt = balance * risk_per_trade
        sl_pips = abs(entry - sl_price) / pip_size
        if sl_pips == 0:
            return min_units
        units = risk_amt / (sl_pips * pip_size)
        units = quantize_units(units, int(specs.get("trade_units_precision", 0)))
        return max(int(units), min_units)
    except Exception:
        return min_units


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
    """Compute rounded SL/TP prices from ATR multiples (legacy helper)."""
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
    """Return approximate units for a fixed-risk position size."""
    if balance <= 0 or risk_pct <= 0 or sl_distance_price <= 0:
        return 1

    risk_amount = balance * risk_pct
    distance_pips = sl_distance_price / pip_size(pair)
    value_per_unit_per_pip = pip_value_per_unit if pip_value_per_unit is not None else 0.0001

    if distance_pips <= 0 or value_per_unit_per_pip <= 0:
        return 1

    units = risk_amount / (distance_pips * value_per_unit_per_pip)
    return max(1, int(units))


def is_within_daily_limit(client, account_id: str, max_daily_loss: float = MAX_DAILY_LOSS) -> bool:
    """Return False once current NAV drawdown exceeds the daily cap."""
    try:
        from oandapyV20.endpoints.accounts import AccountSummary

        today = datetime.now(timezone.utc).date().isoformat()
        endpoint = AccountSummary(accountID=account_id)
        response = client.request(endpoint)
        account = response["account"]
        nav = float(account.get("NAV", account.get("balance", 0.0)))

        if today not in _START_OF_DAY_NAV:
            _START_OF_DAY_NAV.clear()
            _START_OF_DAY_NAV[today] = nav

        start_nav = _START_OF_DAY_NAV[today]
        if start_nav <= 0:
            return False

        drawdown = (start_nav - nav) / start_nav
        return drawdown < max_daily_loss
    except Exception:
        return False
