from __future__ import annotations

import json
from storage.db import connect, init_db, write_error, write_gate_snapshot, write_heartbeat


def test_init_db_creates_expected_tables(tmp_path):
    db_path = tmp_path / "phase_d1.sqlite"
    conn = connect(db_path)
    try:
        init_db(conn)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()

    table_names = {row[0] for row in rows}
    assert {"bot_status", "gate_snapshots", "errors"}.issubset(table_names)


def test_write_heartbeat_inserts_row(tmp_path):
    conn = connect(tmp_path / "heartbeat.sqlite")
    try:
        init_db(conn)
        write_heartbeat(
            conn,
            mode="OFFLINE",
            version="1.0.0",
            uptime_s=60,
            last_cycle_ts_utc="2025-01-01T00:01:00+00:00",
            paused_pairs=["EUR_USD", "GBP_USD"],
            meta={"source": "unit_test"},
        )
        row = conn.execute(
            """
            SELECT mode, version, uptime_s, last_cycle_ts_utc, paused_pairs_json, meta_json
            FROM bot_status ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "OFFLINE"
    assert row[1] == "1.0.0"
    assert row[2] == 60
    assert row[3] == "2025-01-01T00:01:00+00:00"
    assert json.loads(row[4]) == ["EUR_USD", "GBP_USD"]
    assert json.loads(row[5]) == {"source": "unit_test"}


def test_write_gate_snapshot_inserts_expected_fields(tmp_path):
    conn = connect(tmp_path / "snapshot.sqlite")
    try:
        init_db(conn)
        write_gate_snapshot(
            conn,
            ts_utc="2025-01-01T00:00:00+00:00",
            pair="EUR_USD",
            strategy="ema_vwap",
            session_ok=True,
            spread_ok=False,
            news_ok=True,
            open_pos_ok=False,
            daily_ok=True,
            enemy_ok=True,
            final_signal="HOLD",
            reason="spread_block",
            details={"spread_pips": 3.2},
        )
        row = conn.execute(
            """
            SELECT ts_utc, pair, strategy, session_ok, spread_ok, news_ok,
                   open_pos_ok, daily_ok, enemy_ok, final_signal, reason, details_json
            FROM gate_snapshots ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "2025-01-01T00:00:00+00:00"
    assert row[1] == "EUR_USD"
    assert row[2] == "ema_vwap"
    assert row[3:9] == (1, 0, 1, 0, 1, 1)
    assert row[9] == "HOLD"
    assert row[10] == "spread_block"
    assert json.loads(row[11]) == {"spread_pips": 3.2}


def test_write_error_inserts_row(tmp_path):
    conn = connect(tmp_path / "errors.sqlite")
    try:
        init_db(conn)
        write_error(conn, component="risk_manager", message="daily loss exceeded", details={"drawdown": 0.031})
        row = conn.execute("SELECT component, message, details_json FROM errors ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "risk_manager"
    assert row[1] == "daily loss exceeded"
    assert json.loads(row[2]) == {"drawdown": 0.031}
