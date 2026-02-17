"""Unit tests for session gate behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from filters.session_filter import is_session_active


def test_session_start_is_inclusive() -> None:
    now = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert is_session_active("EUR_USD", now_utc=now) is True


def test_session_end_is_exclusive() -> None:
    now = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)
    assert is_session_active("EUR_USD", now_utc=now) is False


def test_unknown_pair_is_inactive() -> None:
    now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert is_session_active("AUD_CAD", now_utc=now) is False
