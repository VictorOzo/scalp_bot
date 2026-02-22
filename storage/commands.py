"""Command queue helpers for dashboard control-plane operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
FINAL_STATUSES = {STATUS_SUCCEEDED, STATUS_FAILED, STATUS_SKIPPED}


def _utc_now_iso() -> str:
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
        (_utc_now_iso(), actor, type, _dump_json(payload), idempotency_key, STATUS_PENDING),
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


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
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
        "handled_by": row[10],
    }


def fetch_next_pending(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, created_ts_utc, actor, type, payload_json, idempotency_key, status,
               started_ts_utc, finished_ts_utc, result_json, handled_by
        FROM commands
        WHERE status = ?
        ORDER BY created_ts_utc ASC, id ASC
        LIMIT 1
        """,
        (STATUS_PENDING,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def claim_next_pending(conn: sqlite3.Connection, *, handled_by: str) -> dict[str, Any] | None:
    row = fetch_next_pending(conn)
    if row is None:
        return None

    updated = conn.execute(
        """
        UPDATE commands
        SET status = ?, started_ts_utc = ?, handled_by = ?
        WHERE id = ? AND status = ?
        """,
        (STATUS_RUNNING, _utc_now_iso(), handled_by, int(row["id"]), STATUS_PENDING),
    )
    if updated.rowcount != 1:
        conn.commit()
        return None

    _write_audit_log(
        conn,
        actor=handled_by,
        action="COMMAND_CLAIMED",
        command_id=int(row["id"]),
        details={"previous_status": STATUS_PENDING},
    )
    _write_audit_log(
        conn,
        actor=handled_by,
        action="COMMAND_EXECUTION_STARTED",
        command_id=int(row["id"]),
        details={"type": row["type"]},
    )
    conn.commit()

    refreshed = conn.execute(
        """
        SELECT id, created_ts_utc, actor, type, payload_json, idempotency_key, status,
               started_ts_utc, finished_ts_utc, result_json, handled_by
        FROM commands
        WHERE id = ?
        """,
        (int(row["id"]),),
    ).fetchone()
    return _row_to_dict(refreshed) if refreshed else None


def mark_command_running(conn: sqlite3.Connection, command_id: int, *, handled_by: str | None = None) -> None:
    conn.execute(
        """
        UPDATE commands
        SET status = ?, started_ts_utc = COALESCE(started_ts_utc, ?), handled_by = COALESCE(handled_by, ?)
        WHERE id = ?
        """,
        (STATUS_RUNNING, _utc_now_iso(), handled_by, command_id),
    )
    conn.commit()


def mark_command_finished(
    conn: sqlite3.Connection,
    command_id: int,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    actor: str | None = None,
) -> None:
    if status not in FINAL_STATUSES:
        raise ValueError(f"Invalid terminal status: {status}")

    command_row = conn.execute("SELECT actor, type FROM commands WHERE id = ?", (command_id,)).fetchone()
    resolved_actor = actor or (command_row[0] if command_row else "unknown")

    conn.execute(
        """
        UPDATE commands
        SET status = ?, finished_ts_utc = ?, result_json = ?
        WHERE id = ?
        """,
        (status, _utc_now_iso(), _dump_json(result), command_id),
    )
    _write_audit_log(
        conn,
        actor=resolved_actor,
        action="COMMAND_COMPLETED",
        command_id=command_id,
        details={"status": status, "result": result},
    )
    conn.commit()


def mark_command_done(conn: sqlite3.Connection, command_id: int, result: dict[str, Any] | None = None) -> None:
    mark_command_finished(conn, command_id, status=STATUS_SUCCEEDED, result=result)


def mark_command_failed(
    conn: sqlite3.Connection,
    command_id: int,
    error: str,
    result: dict[str, Any] | None = None,
) -> None:
    result_payload = dict(result or {})
    result_payload["error"] = error
    mark_command_finished(conn, command_id, status=STATUS_FAILED, result=result_payload)


def fail_stale_running_commands(conn: sqlite3.Connection, *, timeout_sec: float, handled_by: str) -> list[int]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_sec)).isoformat()
    rows = conn.execute(
        "SELECT id FROM commands WHERE status = ? AND started_ts_utc IS NOT NULL AND started_ts_utc < ?",
        (STATUS_RUNNING, cutoff),
    ).fetchall()
    stale_ids = [int(row[0]) for row in rows]
    for command_id in stale_ids:
        mark_command_finished(
            conn,
            command_id,
            status=STATUS_FAILED,
            actor=handled_by,
            result={"error": "stale RUNNING command timed out"},
        )
    return stale_ids


def list_recent_commands(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, created_ts_utc, actor, type, payload_json, idempotency_key, status,
               started_ts_utc, finished_ts_utc, result_json, handled_by
        FROM commands
        ORDER BY created_ts_utc DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]
