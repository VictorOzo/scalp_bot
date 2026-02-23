"""Runtime operational helpers: heartbeat stale checks and SQLite backups."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def stale_threshold_seconds() -> int:
    return int(os.getenv("BOT_HEARTBEAT_STALE_SECONDS", "30"))


def is_heartbeat_stale(*, last_heartbeat_at: str | None, now: datetime | None = None, threshold_seconds: int | None = None) -> bool:
    if not last_heartbeat_at:
        return True
    threshold = threshold_seconds if threshold_seconds is not None else stale_threshold_seconds()
    try:
        parsed = datetime.fromisoformat(last_heartbeat_at)
    except ValueError:
        return True
    ref_now = now or datetime.now(timezone.utc)
    return (ref_now - parsed) > timedelta(seconds=threshold)


def run_sqlite_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = backup_dir / f"{db_path.stem}_{stamp}.sqlite"

    src_conn = sqlite3.connect(db_path)
    try:
        dst_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dest


def prune_old_backups(backup_dir: Path, *, retention_days: int) -> list[Path]:
    if not backup_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed: list[Path] = []
    for path in backup_dir.glob("*.sqlite"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink(missing_ok=True)
            removed.append(path)
    return removed


def maybe_backup_sqlite(db_path: Path) -> Path | None:
    enabled = os.getenv("SQLITE_BACKUP_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled or not db_path.exists():
        return None
    backup_dir = Path(os.getenv("SQLITE_BACKUP_DIR", "backups"))
    retention = int(os.getenv("SQLITE_BACKUP_RETENTION_DAYS", "7"))

    today_marker = backup_dir / ".last_backup_day"
    today = datetime.now(timezone.utc).date().isoformat()
    if today_marker.exists() and today_marker.read_text(encoding="utf-8").strip() == today:
        return None

    backup_path = run_sqlite_backup(db_path, backup_dir)
    prune_old_backups(backup_dir, retention_days=retention)
    today_marker.write_text(today, encoding="utf-8")
    return backup_path
