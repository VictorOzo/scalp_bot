"""SQLite storage utilities for dashboard state and telemetry."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_ENV_VAR = "SCALP_BOT_DB_PATH"
DEFAULT_DB_PATH = Path("storage/scalp_bot.sqlite")


def get_db_path() -> Path:
    """Return the configured SQLite path from env or default location."""
    configured = os.getenv(DB_ENV_VAR)
    return Path(configured) if configured else DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection, creating parent directories when needed."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def init_db(conn: sqlite3.Connection) -> None:
    """Create dashboard storage tables and indexes if they do not already exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS bot_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            mode TEXT NOT NULL,
            version TEXT,
            uptime_s INTEGER,
            last_cycle_ts_utc TEXT,
            paused_pairs_json TEXT,
            meta_json TEXT
        );

        CREATE TABLE IF NOT EXISTS gate_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            pair TEXT NOT NULL,
            strategy TEXT NOT NULL,
            session_ok INTEGER NOT NULL,
            spread_ok INTEGER NOT NULL,
            news_ok INTEGER NOT NULL,
            open_pos_ok INTEGER NOT NULL,
            daily_ok INTEGER NOT NULL,
            enemy_ok INTEGER NOT NULL,
            final_signal TEXT NOT NULL,
            reason TEXT,
            details_json TEXT
        );

        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            component TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT
        );

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_ts_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            type TEXT NOT NULL,
            payload_json TEXT,
            idempotency_key TEXT,
            status TEXT NOT NULL,
            started_ts_utc TEXT,
            finished_ts_utc TEXT,
            result_json TEXT,
            handled_by TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            command_id INTEGER,
            details_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_gate_snapshots_ts_utc
        ON gate_snapshots(ts_utc);

        CREATE INDEX IF NOT EXISTS idx_gate_snapshots_pair_ts_utc
        ON gate_snapshots(pair, ts_utc);

        CREATE INDEX IF NOT EXISTS idx_bot_status_ts_utc
        ON bot_status(ts_utc);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_commands_idempotency_key
        ON commands(idempotency_key)
        WHERE idempotency_key IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_commands_status_created_ts
        ON commands(status, created_ts_utc);

        CREATE INDEX IF NOT EXISTS idx_audit_log_ts_utc
        ON audit_log(ts_utc);

        CREATE INDEX IF NOT EXISTS idx_audit_log_command_id
        ON audit_log(command_id);
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(commands)").fetchall()}
    if "handled_by" not in columns:
        conn.execute("ALTER TABLE commands ADD COLUMN handled_by TEXT")
    conn.commit()


def _dump_json(value: dict[str, Any] | list[str] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def write_heartbeat(
    conn: sqlite3.Connection,
    *,
    mode: str,
    version: str | None,
    uptime_s: int | None,
    last_cycle_ts_utc: str | None,
    paused_pairs: list[str] | None,
    meta: dict[str, Any] | None,
) -> None:
    """Insert a bot heartbeat/status row into the bot_status table."""
    conn.execute(
        """
        INSERT INTO bot_status (
            ts_utc, mode, version, uptime_s, last_cycle_ts_utc, paused_pairs_json, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now_iso(),
            mode,
            version,
            uptime_s,
            last_cycle_ts_utc,
            _dump_json(paused_pairs),
            _dump_json(meta),
        ),
    )
    conn.commit()


def write_gate_snapshot(
    conn: sqlite3.Connection,
    *,
    ts_utc: str,
    pair: str,
    strategy: str,
    session_ok: bool,
    spread_ok: bool,
    news_ok: bool,
    open_pos_ok: bool,
    daily_ok: bool,
    enemy_ok: bool,
    final_signal: str,
    reason: str | None,
    details: dict[str, Any] | None,
) -> None:
    """Insert one per-pair gate outcome and resulting signal decision."""
    conn.execute(
        """
        INSERT INTO gate_snapshots (
            ts_utc, pair, strategy, session_ok, spread_ok, news_ok, open_pos_ok,
            daily_ok, enemy_ok, final_signal, reason, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts_utc,
            pair,
            strategy,
            int(session_ok),
            int(spread_ok),
            int(news_ok),
            int(open_pos_ok),
            int(daily_ok),
            int(enemy_ok),
            final_signal,
            reason,
            _dump_json(details),
        ),
    )
    conn.commit()


def write_error(conn: sqlite3.Connection, *, component: str, message: str, details: dict[str, Any] | None) -> None:
    """Insert an error record for monitoring and dashboard inspection."""
    conn.execute(
        """
        INSERT INTO errors (ts_utc, component, message, details_json)
        VALUES (?, ?, ?, ?)
        """,
        (utc_now_iso(), component, message, _dump_json(details)),
    )
    conn.commit()
