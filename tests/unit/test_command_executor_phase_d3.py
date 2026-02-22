from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from execution import command_executor
from execution.trade_store import TradeStore
from storage.commands import enqueue_command
from storage.db import connect, init_db
from tests.tools._cycle_once import run_cycle_once


def _setup(tmp_path):
    db_path = tmp_path / "phase_d3_unit.sqlite"
    conn = connect(db_path)
    init_db(conn)
    store = TradeStore(db_path)
    store.init_db()
    return conn, store


def test_close_pair_paper_closes_without_broker_and_audits(tmp_path):
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

        calls = {"n": 0}

        def _broker(pair: str):
            calls["n"] += 1
            return {"pair": pair}

        _, result = command_executor.process_next_command(
            conn,
            paused_pairs=set(),
            handled_by="bot-1",
            trade_store=store,
            live_close_fn=_broker,
        )

        status = conn.execute("SELECT status FROM commands WHERE id = ?", (command_id,)).fetchone()[0]
        trade_closed = conn.execute("SELECT COUNT(*) FROM trades WHERE pair='EUR_USD' AND time_close_utc IS NOT NULL").fetchone()[0]
        audit_count = conn.execute("SELECT COUNT(*) FROM audit_log WHERE command_id = ?", (command_id,)).fetchone()[0]
    finally:
        conn.close()

    assert result is not None
    assert result["status"] == "SUCCEEDED"
    assert status == "SUCCEEDED"
    assert calls["n"] == 0
    assert trade_closed == 1
    assert audit_count >= 4


def test_close_pair_live_enabled_calls_broker_once(tmp_path, monkeypatch):
    conn, store = _setup(tmp_path)
    try:
        monkeypatch.setattr(command_executor, "LIVE_TRADING_ENABLED", True)
        command_id = enqueue_command(conn, actor="admin", type="CLOSE_PAIR", payload={"pair": "GBP_USD", "mode": "LIVE"})
        calls: list[str] = []

        def _broker(pair: str):
            calls.append(pair)
            return {"ok": True}

        command_executor.process_next_command(
            conn,
            paused_pairs=set(),
            handled_by="bot-live",
            trade_store=store,
            live_close_fn=_broker,
        )
        row = conn.execute("SELECT status, result_json FROM commands WHERE id = ?", (command_id,)).fetchone()
    finally:
        conn.close()

    assert calls == ["GBP_USD"]
    assert row[0] == "SUCCEEDED"
    assert json.loads(row[1])["mode"] == "LIVE"


def test_close_pair_live_disabled_skips_broker(tmp_path, monkeypatch):
    conn, store = _setup(tmp_path)
    try:
        monkeypatch.setattr(command_executor, "LIVE_TRADING_ENABLED", False)
        command_id = enqueue_command(conn, actor="admin", type="CLOSE_PAIR", payload={"pair": "USD_JPY", "mode": "LIVE"})
        calls = {"n": 0}

        def _broker(pair: str):
            calls["n"] += 1
            return {"ok": True}

        command_executor.process_next_command(
            conn,
            paused_pairs=set(),
            handled_by="bot-live",
            trade_store=store,
            live_close_fn=_broker,
        )
        row = conn.execute("SELECT status, result_json FROM commands WHERE id = ?", (command_id,)).fetchone()
    finally:
        conn.close()

    assert calls["n"] == 0
    assert row[0] == "SKIPPED"
    assert "LIVE trading disabled" in json.loads(row[1])["reason"]


def test_paused_pair_skips_strategy_and_writes_gate_snapshot(tmp_path):
    conn, _ = _setup(tmp_path)
    try:
        enqueue_command(conn, actor="admin", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        evaluated: list[str] = []
        run_cycle_once(
            conn,
            pairs=["EUR_USD", "GBP_USD"],
            now_utc=datetime.now(timezone.utc),
            strategy_eval=lambda pair: evaluated.append(pair),
        )
        snapshot = conn.execute(
            "SELECT pair, reason, details_json FROM gate_snapshots WHERE pair='EUR_USD' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert evaluated == ["GBP_USD"]
    assert snapshot[1] == "paused"
    details = json.loads(snapshot[2])
    assert details["paused"] is True
    assert details["pair"] == "EUR_USD"


def test_stale_running_command_marked_failed(tmp_path):
    conn, _ = _setup(tmp_path)
    try:
        command_id = enqueue_command(conn, actor="admin", type="PAUSE_PAIR", payload={"pair": "EUR_USD"})
        stale_started = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        conn.execute(
            "UPDATE commands SET status='RUNNING', started_ts_utc=?, handled_by='old-bot' WHERE id=?",
            (stale_started, command_id),
        )
        conn.commit()

        run_cycle_once(conn, pairs=["EUR_USD"], now_utc=datetime.now(timezone.utc), handled_by="new-bot")
        row = conn.execute("SELECT status FROM commands WHERE id = ?", (command_id,)).fetchone()
    finally:
        conn.close()

    assert row[0] == "FAILED"
