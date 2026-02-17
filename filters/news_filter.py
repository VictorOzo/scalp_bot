"""News-event gate with offline-first behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

PAIR_CURRENCIES: dict[str, list[str]] = {
    "EUR_USD": ["EUR", "USD"],
    "GBP_USD": ["GBP", "USD"],
    "USD_JPY": ["USD", "JPY"],
}


def _parse_event_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_news_clear(
    pair: str,
    now_utc: datetime | None = None,
    buffer_minutes: int = 15,
    events: list[dict[str, Any]] | None = None,
) -> bool:
    """Return True when no blocking high-impact events are near current time."""
    if events is None:
        return True

    currencies = PAIR_CURRENCIES.get(pair)
    if not currencies:
        return True

    current_time = now_utc or datetime.now(timezone.utc)
    window = timedelta(minutes=buffer_minutes)

    for event in events:
        if event.get("impact") != "High":
            continue
        if event.get("currency") not in currencies:
            continue

        raw_time = event.get("time")
        if not raw_time or not isinstance(raw_time, str):
            continue

        event_time = _parse_event_time(raw_time)
        if abs(event_time - current_time) <= window:
            return False

    return True


def fetch_forexfactory_calendar(timeout_s: int = 5) -> list[dict[str, Any]]:
    """Fetch ForexFactory calendar JSON using optional requests dependency."""
    try:
        import requests
    except ImportError as exc:
        raise ImportError("requests is required to fetch ForexFactory calendar") from exc

    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    response = requests.get(url, timeout=timeout_s)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected calendar payload format")
    return payload
