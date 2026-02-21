"""Command queue helpers for dashboard control-plane operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

ALLOWED_COMMAND_TYPES = {
    "PAUSE_PAIR",
    "RESUME_PAIR",
    "PAUSE_ALL",
    "RESUME_ALL",
    "CLOSE_PAIR",
    "CLOSE_ALL",
    "RELOAD_PARAMS",
}


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _dump_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def _load_json(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


def _write_audit_log(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    command_id: int | None,
    details: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (ts_utc, actor, action, command_id, details_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (_utc_now_iso(), actor, action, command_id, _dump_json(details)),
    )


def enqueue_command(
    conn: sqlite3.Connection,
    *,
    actor: str,
    type: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> int:
    """Insert a pending command and audit record, honoring optional idempotency."""
    if type not in ALLOWED_COMMAND_TYPES:
        raise ValueError(f"Unsupported command type: {type}")

    existing_id: int | None = None
    if idempotency_key is not None:
        row = conn.execute("SELECT id FROM commands WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if row is not None:
            existing_id = int(row[0])

    if existing_id is not None:
        return existing_id

    cursor = conn.execute(
        """
        INSERT INTO commands (
            created_ts_utc, actor, type, payload_json, idempotency_key, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (_utc_now_iso(), actor, type, _dump_json(payload), idempotency_key, "pending"),
    )
    command_id = int(cursor.lastrowid)
    _write_audit_log(
        conn,
        actor=actor,
        action="COMMAND_ENQUEUED",
        command_id=command_id,
        details={"type": type, "idempotency_key": idempotency_key},
    )
    conn.commit()
    return command_id


def fetch_next_pending(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the oldest pending command as a dictionary, or None when queue is empty."""
    row = conn.execute(
        """
        SELECT id, created_ts_utc, actor, type, payload_json, idempotency_key, status,
               started_ts_utc, finished_ts_utc, result_json
        FROM commands
        WHERE status = 'pending'
        ORDER BY created_ts_utc ASC, id ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None

    return {
        "id": int(row[0]),
        "created_ts_utc": row[1],
        "actor": row[2],
        "type": row[3],
        "payload": _load_json(row[4]),
        "idempotency_key": row[5],
        "status": row[6],
        "started_ts_utc": row[7],
        "finished_ts_utc": row[8],
        "result": _load_json(row[9]),
    }


def mark_command_running(conn: sqlite3.Connection, command_id: int) -> None:
    """Mark a command as running and set start timestamp."""
    conn.execute(
        """
        UPDATE commands
        SET status = 'running', started_ts_utc = ?
        WHERE id = ?
        """,
        (_utc_now_iso(), command_id),
    )
    conn.commit()


def mark_command_done(conn: sqlite3.Connection, command_id: int, result: dict[str, Any] | None = None) -> None:
    """Mark a command as done, persist result JSON, and append an audit row."""
    command_row = conn.execute("SELECT actor FROM commands WHERE id = ?", (command_id,)).fetchone()
    actor = command_row[0] if command_row else "unknown"

    conn.execute(
        """
        UPDATE commands
        SET status = 'done', finished_ts_utc = ?, result_json = ?
        WHERE id = ?
        """,
        (_utc_now_iso(), _dump_json(result), command_id),
    )
    _write_audit_log(
        conn,
        actor=actor,
        action="COMMAND_DONE",
        command_id=command_id,
        details=result,
    )
    conn.commit()


def mark_command_failed(
    conn: sqlite3.Connection,
    command_id: int,
    error: str,
    result: dict[str, Any] | None = None,
) -> None:
    """Mark a command as failed, persist error details, and append an audit row."""
    command_row = conn.execute("SELECT actor FROM commands WHERE id = ?", (command_id,)).fetchone()
    actor = command_row[0] if command_row else "unknown"

    result_payload = dict(result or {})
    result_payload["error"] = error
    conn.execute(
        """
        UPDATE commands
        SET status = 'failed', finished_ts_utc = ?, result_json = ?
        WHERE id = ?
        """,
        (_utc_now_iso(), _dump_json(result_payload), command_id),
    )
    _write_audit_log(
        conn,
        actor=actor,
        action="COMMAND_FAILED",
        command_id=command_id,
        details=result_payload,
    )
    conn.commit()


def list_recent_commands(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """Return latest commands ordered by creation descending for tools and debugging."""
    rows = conn.execute(
        """
        SELECT id, created_ts_utc, actor, type, payload_json, idempotency_key, status,
               started_ts_utc, finished_ts_utc, result_json
        FROM commands
        ORDER BY created_ts_utc DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "created_ts_utc": row[1],
            "actor": row[2],
            "type": row[3],
            "payload": _load_json(row[4]),
            "idempotency_key": row[5],
            "status": row[6],
            "started_ts_utc": row[7],
            "finished_ts_utc": row[8],
            "result": _load_json(row[9]),
        }
        for row in rows
    ]
