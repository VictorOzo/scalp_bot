from __future__ import annotations

from datetime import datetime, timedelta, timezone

from execution.runtime_ops import is_heartbeat_stale


def test_stale_true_when_older_than_threshold() -> None:
    now = datetime.now(timezone.utc)
    old = (now - timedelta(seconds=31)).isoformat()
    assert is_heartbeat_stale(last_heartbeat_at=old, now=now, threshold_seconds=30) is True


def test_stale_false_on_boundary() -> None:
    now = datetime.now(timezone.utc)
    exact = (now - timedelta(seconds=30)).isoformat()
    assert is_heartbeat_stale(last_heartbeat_at=exact, now=now, threshold_seconds=30) is False


def test_stale_true_without_heartbeat() -> None:
    assert is_heartbeat_stale(last_heartbeat_at=None, threshold_seconds=30) is True
