# storage/db.py
"""
SQLite storage utilities for dashboard state and telemetry.
"""

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
    """
    Open a SQLite connection, creating parent directories when needed.

    Why:
    FastAPI may create/close dependency resources in different threads.
    SQLite connections are thread-bound unless check_same_thread=False.
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_table(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({ddl})")


def _ensure_column(conn: sqlite3.Connection, table: str, column_ddl: str) -> None:
    """
    Add a column if missing.

    Notes:
    - SQLite supports ADD COLUMN with limited constraint support.
    - Avoid adding NOT NULL without DEFAULT to existing tables.
    """
    col_name = column_ddl.strip().split()[0]
    cols = _table_columns(conn, table)
    if col_name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    """
    Create storage tables and indexes if they do not already exist.

    IMPORTANT:
    - Migrations must run BEFORE creating indexes that reference new columns.
    - This function is safe to call repeatedly.
    """
    # --- Core tables (no indexes that depend on future migrations) ---
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

        CREATE TABLE IF NOT EXISTS bot_runtime (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_heartbeat_at TEXT,
            last_restart_at TEXT,
            startup_time_utc TEXT,
            handled_by TEXT,
            version TEXT
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

        -- Positions table: create if missing (schema aligned to api/routes/positions.py)
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            strategy TEXT,
            direction TEXT,
            units REAL,
            entry_price REAL,
            sl_price REAL,
            tp_price REAL,
            time_open_utc TEXT,
            is_open INTEGER NOT NULL DEFAULT 1,
            meta_json TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_ts_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_ts_utc TEXT NOT NULL,
            updated_by TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            profile TEXT NOT NULL,
            params_json TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            updated_ts_utc TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            UNIQUE(strategy_name, profile)
        );
        """
    )

    # --- Migrations (add missing columns safely) ---
    _ensure_column(conn, "commands", "handled_by TEXT")

    # positions columns required by /positions route
    _ensure_column(conn, "positions", "direction TEXT")
    _ensure_column(conn, "positions", "strategy TEXT")
    _ensure_column(conn, "positions", "sl_price REAL")
    _ensure_column(conn, "positions", "tp_price REAL")
    _ensure_column(conn, "positions", "units REAL")
    _ensure_column(conn, "positions", "entry_price REAL")
    _ensure_column(conn, "positions", "time_open_utc TEXT")
    _ensure_column(conn, "positions", "is_open INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "positions", "meta_json TEXT")

    conn.commit()

    from storage.strategy_params import seed_defaults

    seed_defaults(conn)

    # --- Indexes (safe after migrations) ---
    conn.executescript(
        """
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

        CREATE INDEX IF NOT EXISTS idx_users_username
        ON users(username);

        CREATE INDEX IF NOT EXISTS idx_strategy_params_strategy
        ON strategy_params(strategy_name);

        CREATE INDEX IF NOT EXISTS idx_strategy_params_active
        ON strategy_params(strategy_name, is_active);
        """
    )

    # Positions indexes: only create those whose columns exist (defensive)
    pos_cols = _table_columns(conn, "positions")

    if "time_open_utc" in pos_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_time_open_utc ON positions(time_open_utc)"
        )

    if "pair" in pos_cols and "time_open_utc" in pos_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_pair_time_open_utc ON positions(pair, time_open_utc)"
        )

    if "is_open" in pos_cols and "time_open_utc" in pos_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_is_open_time_open_utc ON positions(is_open, time_open_utc)"
        )

    conn.commit()



def ping(conn: sqlite3.Connection) -> bool:
    """Return True when DB responds to a simple ping query."""
    try:
        conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def get_app_settings(conn: sqlite3.Connection, keys: list[str] | None = None) -> dict[str, Any]:
    """Load settings values from app_settings table."""
    if keys:
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"SELECT key, value_json FROM app_settings WHERE key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
    else:
        rows = conn.execute("SELECT key, value_json FROM app_settings").fetchall()
    out: dict[str, Any] = {}
    for row in rows:
        out[str(row[0])] = json.loads(row[1])
    return out

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
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO bot_status (
            ts_utc, mode, version, uptime_s, last_cycle_ts_utc, paused_pairs_json, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            mode,
            version,
            uptime_s,
            last_cycle_ts_utc,
            _dump_json(paused_pairs),
            _dump_json(meta),
        ),
    )
    conn.execute(
        """
        INSERT INTO bot_runtime (id, last_heartbeat_at, version)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_heartbeat_at = excluded.last_heartbeat_at,
            version = COALESCE(excluded.version, bot_runtime.version)
        """,
        (now, version),
    )
    conn.commit()



def mark_bot_restart(conn: sqlite3.Connection, *, startup_time_utc: str | None = None, handled_by: str | None = None, version: str | None = None) -> None:
    started = startup_time_utc or utc_now_iso()
    conn.execute(
        """
        INSERT INTO bot_runtime (id, last_restart_at, startup_time_utc, handled_by, version)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_restart_at = excluded.last_restart_at,
            startup_time_utc = excluded.startup_time_utc,
            handled_by = excluded.handled_by,
            version = COALESCE(excluded.version, bot_runtime.version)
        """,
        (started, started, handled_by, version),
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