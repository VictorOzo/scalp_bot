from __future__ import annotations

import json

from storage.commands import (
    enqueue_command,
    fetch_next_pending,
    mark_command_done,
    mark_command_failed,
    mark_command_running,
)
from storage.db import connect, init_db


def test_enqueue_command_inserts_pending(tmp_path):
    conn = connect(tmp_path / "commands.sqlite")
    try:
        init_db(conn)
        command_id = enqueue_command(conn, actor="local", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        row = conn.execute("SELECT status, actor, type, payload_json FROM commands WHERE id = ?", (command_id,)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "pending"
    assert row[1] == "local"
    assert row[2] == "PAUSE_PAIR"
    assert json.loads(row[3]) == {"pair": "EUR_USD"}


def test_enqueue_command_idempotency_returns_existing_id(tmp_path):
    conn = connect(tmp_path / "commands.sqlite")
    try:
        init_db(conn)
        first_id = enqueue_command(
            conn,
            actor="local",
            type="PAUSE_PAIR",
            payload={"pair": "EUR_USD"},
            idempotency_key="k1",
        )
        second_id = enqueue_command(
            conn,
            actor="local",
            type="PAUSE_PAIR",
            payload={"pair": "EUR_USD"},
            idempotency_key="k1",
        )
        count = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    finally:
        conn.close()

    assert first_id == second_id
    assert count == 1


def test_fetch_next_pending_returns_oldest(tmp_path):
    conn = connect(tmp_path / "commands.sqlite")
    try:
        init_db(conn)
        first_id = enqueue_command(conn, actor="local", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        enqueue_command(conn, actor="local", type="PAUSE_PAIR", payload={"pair": "GBP_USD"})
        next_cmd = fetch_next_pending(conn)
    finally:
        conn.close()

    assert next_cmd is not None
    assert next_cmd["id"] == first_id
    assert next_cmd["payload"] == {"pair": "EUR_USD"}


def test_command_status_transitions(tmp_path):
    conn = connect(tmp_path / "commands.sqlite")
    try:
        init_db(conn)
        command_id = enqueue_command(conn, actor="local", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})

        mark_command_running(conn, command_id)
        running = conn.execute("SELECT status, started_ts_utc FROM commands WHERE id = ?", (command_id,)).fetchone()

        mark_command_done(conn, command_id, result={"ok": True})
        done = conn.execute("SELECT status, finished_ts_utc FROM commands WHERE id = ?", (command_id,)).fetchone()

        failed_id = enqueue_command(conn, actor="local", type="RESUME_PAIR", payload={"pair": "EUR_USD"})
        mark_command_failed(conn, failed_id, error="boom", result={"retry": False})
        failed = conn.execute("SELECT status, result_json FROM commands WHERE id = ?", (failed_id,)).fetchone()
    finally:
        conn.close()

    assert running[0] == "running"
    assert running[1] is not None
    assert done[0] == "done"
    assert done[1] is not None
    assert failed[0] == "failed"
    assert json.loads(failed[1])["error"] == "boom"


def test_audit_log_written_for_enqueue_done_and_failed(tmp_path):
    conn = connect(tmp_path / "commands.sqlite")
    try:
        init_db(conn)
        command_id = enqueue_command(conn, actor="admin:test", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        enqueue_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        mark_command_done(conn, command_id, result={"ok": True})
        done_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        failed_id = enqueue_command(conn, actor="admin:test", type="RESUME_PAIR", payload={"pair": "EUR_USD"})
        mark_command_failed(conn, failed_id, error="not_allowed")
        failed_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    finally:
        conn.close()

    assert enqueue_count == 1
    assert done_count == 2
    assert failed_count == 4
