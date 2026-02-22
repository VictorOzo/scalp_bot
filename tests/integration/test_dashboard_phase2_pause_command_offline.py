from __future__ import annotations

from datetime import datetime, timezone

from storage.commands import enqueue_command
from storage.db import connect, init_db
from tests.tools._cycle_once import run_cycle_once


def test_pause_command_lifecycle_and_gate_effect_offline(tmp_path):
    conn = connect(tmp_path / "phase2.sqlite")
    try:
        init_db(conn)
        command_id = enqueue_command(
            conn,
            actor="admin:test",
            type="PAUSE_PAIR",
            payload={"pair": "EUR_USD"},
            idempotency_key="t1",
        )

        run_cycle_once(conn, pairs=["EUR_USD", "GBP_USD"], now_utc=datetime.now(timezone.utc), offline=True)

        command_row = conn.execute("SELECT status, result_json FROM commands WHERE id = ?", (command_id,)).fetchone()
        done_audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE command_id = ? AND action = 'COMMAND_COMPLETED'",
            (command_id,),
        ).fetchone()[0]
        snapshot = conn.execute(
            """
            SELECT final_signal, reason
            FROM gate_snapshots
            WHERE pair = 'EUR_USD'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert command_row is not None
    assert command_row[0] == "SUCCEEDED"
    assert "EUR_USD" in command_row[1]
    assert done_audit_count == 1
    assert snapshot == ("HOLD", "paused")
