"""Unit tests for news filter."""

from __future__ import annotations

from datetime import datetime, timezone

from filters.news_filter import is_news_clear


NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_events_none_allows_trading() -> None:
    assert is_news_clear("EUR_USD", now_utc=NOW, events=None) is True


def test_high_impact_within_buffer_blocks() -> None:
    events = [{"impact": "High", "currency": "USD", "time": "2024-01-01T12:10:00Z"}]
    assert is_news_clear("EUR_USD", now_utc=NOW, buffer_minutes=15, events=events) is False


def test_low_impact_is_ignored() -> None:
    events = [{"impact": "Low", "currency": "USD", "time": "2024-01-01T12:05:00+00:00"}]
    assert is_news_clear("EUR_USD", now_utc=NOW, events=events) is True


def test_unrelated_currency_is_ignored() -> None:
    events = [{"impact": "High", "currency": "AUD", "time": "2024-01-01T12:05:00Z"}]
    assert is_news_clear("EUR_USD", now_utc=NOW, events=events) is True


def test_high_impact_outside_buffer_is_allowed() -> None:
    events = [{"impact": "High", "currency": "USD", "time": "2024-01-01T12:40:00Z"}]
    assert is_news_clear("EUR_USD", now_utc=NOW, buffer_minutes=15, events=events) is True
