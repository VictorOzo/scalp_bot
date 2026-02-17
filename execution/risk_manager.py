"""Risk management helpers."""

from __future__ import annotations

from datetime import datetime, timezone

_START_OF_DAY_NAV: dict[str, float] = {}


def calculate_position_size() -> float:
    """Calculate position sizing (not implemented in this phase)."""
    raise NotImplementedError("calculate_position_size is not implemented yet.")


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
