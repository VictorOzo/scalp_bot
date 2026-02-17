"""News-event gate with offline-first behavior (ForexFactory compatible)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Final

PAIR_CURRENCIES: Final[dict[str, list[str]]] = {
    "EUR_USD": ["EUR", "USD"],
    "GBP_USD": ["GBP", "USD"],
    "USD_JPY": ["USD", "JPY"],
}
BLOCK_IMPACTS: Final[set[str]] = {"High"}


def _parse_event_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_blocking_news_event(
    pair: str,
    now_utc: datetime | None = None,
    buffer_minutes: int = 15,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return the first blocking High-impact event within the configured window."""
    if events is None:
        return None

    currencies = PAIR_CURRENCIES.get(pair)
    if not currencies:
        return None

    current_time = now_utc or datetime.now(timezone.utc)
    window = timedelta(minutes=buffer_minutes)

    for event in events:
        impact = event.get("impact")
        if impact not in BLOCK_IMPACTS:
            continue

        currency = event.get("country") or event.get("currency")
        if currency not in currencies:
            continue

        raw_time = event.get("date") or event.get("time")
        if not raw_time or not isinstance(raw_time, str):
            continue

        try:
            event_time = _parse_event_time(raw_time)
        except ValueError:
            continue

        if abs(event_time - current_time) <= window:
            return event

    return None


def is_news_clear(
    pair: str,
    now_utc: datetime | None = None,
    buffer_minutes: int = 15,
    events: list[dict[str, Any]] | None = None,
) -> bool:
    """Return True when no blocking High-impact events are near current time.

    If no events are supplied, this performs a best-effort calendar fetch. Any fetch
    failure is treated as clear (simple offline-first mode).
    """
    resolved_events = events
    if resolved_events is None:
        try:
            resolved_events = fetch_forexfactory_calendar()
        except Exception:
            return True

    return get_blocking_news_event(pair, now_utc, buffer_minutes, resolved_events) is None


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
