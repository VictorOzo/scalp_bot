from __future__ import annotations

from datetime import datetime, timedelta, timezone

from execution.trade_store import TradeStore
from storage.commands import enqueue_command
from storage.db import connect, init_db
from tests.tools._cycle_once import run_cycle_once


def _setup(tmp_path):
    db_path = tmp_path / "phase_d3_integration.sqlite"
    conn = connect(db_path)
    init_db(conn)
    store = TradeStore(db_path)
    store.init_db()
    return conn, store


def test_phase_d3_paper_close_pair_flow(tmp_path):
    conn, store = _setup(tmp_path)
    try:
        store.open_position(
            pair="EUR_USD",
            strategy="ema_vwap",
            direction="BUY",
            units=1000,
            entry_price=1.1,
            sl_price=1.099,
            tp_price=1.102,
        )
        command_id = enqueue_command(conn, actor="admin", type="CLOSE_PAIR", payload={"pair": "EUR_USD", "mode": "PAPER"})
        run_cycle_once(conn, pairs=["EUR_USD"], now_utc=datetime.now(timezone.utc), handled_by="bot-A")

        command_status = conn.execute("SELECT status FROM commands WHERE id=?", (command_id,)).fetchone()[0]
        open_positions = store.list_open_positions()
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE pair='EUR_USD' AND time_close_utc IS NOT NULL").fetchone()[0]
        audit_rows = conn.execute("SELECT COUNT(*) FROM audit_log WHERE command_id=?", (command_id,)).fetchone()[0]
    finally:
        conn.close()

    assert command_status == "SUCCEEDED"
    assert open_positions == []
    assert closed_trades == 1
    assert audit_rows >= 4


def test_phase_d3_restart_safety_no_duplicate_actions(tmp_path):
    conn, store = _setup(tmp_path)
    try:
        store.open_position(
            pair="GBP_USD",
            strategy="ema_vwap",
            direction="BUY",
            units=1000,
            entry_price=1.2,
            sl_price=1.199,
            tp_price=1.202,
        )
        enqueue_command(conn, actor="admin", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        done_id = enqueue_command(conn, actor="admin", type="CLOSE_PAIR", payload={"pair": "GBP_USD", "mode": "PAPER"})
        run_cycle_once(conn, pairs=["EUR_USD", "GBP_USD"], now_utc=datetime.now(timezone.utc), handled_by="bot-1")
        run_cycle_once(conn, pairs=["EUR_USD", "GBP_USD"], now_utc=datetime.now(timezone.utc), handled_by="bot-1")

        stale_id = enqueue_command(conn, actor="admin", type="PAUSE_ALL", payload={})
        stale_started = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        conn.execute("UPDATE commands SET status='RUNNING', started_ts_utc=? WHERE id=?", (stale_started, stale_id))
        conn.commit()

        conn.close()
        conn = connect(tmp_path / "phase_d3_integration.sqlite")
        init_db(conn)

        run_cycle_once(conn, pairs=["EUR_USD", "GBP_USD"], now_utc=datetime.now(timezone.utc), handled_by="bot-2")

        done_status = conn.execute("SELECT status FROM commands WHERE id=?", (done_id,)).fetchone()[0]
        stale_status = conn.execute("SELECT status FROM commands WHERE id=?", (stale_id,)).fetchone()[0]
        paused = conn.execute("SELECT paused_pairs_json FROM bot_status ORDER BY id DESC LIMIT 1").fetchone()[0]
        closed_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE pair='GBP_USD' AND time_close_utc IS NOT NULL").fetchone()[0]
        runtime = conn.execute("SELECT startup_time_utc, last_restart_at FROM bot_runtime WHERE id=1").fetchone()
    finally:
        conn.close()

    assert done_status == "SUCCEEDED"
    assert stale_status == "FAILED"
    assert "EUR_USD" in paused
    assert closed_trades == 1
