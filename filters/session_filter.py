"""Session-based trading availability filter."""

from __future__ import annotations

from datetime import datetime, timezone

SESSIONS: dict[str, dict[str, int]] = {
    "EUR_USD": {"start": 8, "end": 17},
    "GBP_USD": {"start": 8, "end": 13},
    "USD_JPY": {"start": 0, "end": 9},
}


def is_session_active(pair: str, now_utc: datetime | None = None) -> bool:
    """Return True when the pair is tradable in its configured UTC session.

    Session boundaries are start-inclusive and end-exclusive.
    Unknown pairs are treated as inactive.
    """
    if pair not in SESSIONS:
        return False

    current_time = now_utc or datetime.now(timezone.utc)
    hour = current_time.hour
    session = SESSIONS[pair]
    return session["start"] <= hour < session["end"]
