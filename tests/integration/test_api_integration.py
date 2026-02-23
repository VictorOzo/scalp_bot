from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import app
from api.auth import ensure_user
from execution.trade_store import TradeStore
from storage.commands import enqueue_command
from storage.db import connect, init_db, write_gate_snapshot, write_heartbeat
from tests.tools._cycle_once import run_cycle_once


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_integration.sqlite"
    monkeypatch.setenv("SCALP_BOT_DB_PATH", str(db_path))
    conn = connect(db_path)
    init_db(conn)
    ensure_user(conn, username="admin", password="admin-pass", role="admin")
    ensure_user(conn, username="viewer", password="viewer-pass", role="viewer")

    now = datetime.now(timezone.utc).isoformat()
    write_heartbeat(
        conn,
        mode="OFFLINE",
        version="test",
        uptime_s=10,
        last_cycle_ts_utc=now,
        paused_pairs=[],
        meta={"integration": True},
    )
    write_gate_snapshot(
        conn,
        ts_utc=now,
        pair="EUR_USD",
        strategy="ema_vwap",
        session_ok=True,
        spread_ok=True,
        news_ok=True,
        open_pos_ok=True,
        daily_ok=True,
        enemy_ok=True,
        final_signal="BUY",
        reason="ok",
        details={"sample": True},
    )

    store = TradeStore(db_path)
    store.init_db()
    store.open_position(
        pair="EUR_USD",
        strategy="ema_vwap",
        direction="BUY",
        units=1000,
        entry_price=1.1,
        sl_price=1.099,
        tp_price=1.102,
    )
    conn.execute(
        "INSERT INTO trades (time_open_utc,time_close_utc,pair,strategy,direction,units,entry_price,exit_price,sl_price,tp_price,result,pnl_pips,pnl_quote,meta_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, now, "EUR_USD", "ema_vwap", "BUY", 1000, 1.1, 1.101, 1.099, 1.102, "TP", 10.0, 1.0, '{"mode":"PAPER"}'),
    )
    conn.commit()
    conn.close()

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> None:
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200


def test_api_endpoints_and_command_pickup(client: TestClient):
    _login(client, "viewer", "viewer-pass")
    status_res = client.get("/status")
    assert status_res.status_code == 200
    assert status_res.json()["last_cycle_ts_utc"] is not None
    assert "is_stale" in status_res.json()

    bot_status_res = client.get("/bot/status")
    assert bot_status_res.status_code == 200
    assert "stale_threshold_seconds" in bot_status_res.json()

    health_res = client.get("/healthz")
    assert health_res.status_code == 200
    assert health_res.json()["ok"] is True

    positions_res = client.get("/positions")
    assert positions_res.status_code == 200
    assert len(positions_res.json()) == 1

    gates_res = client.get("/gates", params={"pair": "EUR_USD"})
    assert gates_res.status_code == 200
    assert len(gates_res.json()) >= 1

    _login(client, "admin", "admin-pass")
    cmd_res = client.post("/commands", json={"type": "PAUSE_PAIR", "payload": {"pair": "EUR_USD"}})
    assert cmd_res.status_code == 200
    command_id = cmd_res.json()["id"]

    conn = connect()
    try:
        init_db(conn)
        run_cycle_once(conn, pairs=["EUR_USD"], now_utc=datetime.now(timezone.utc), handled_by="itest-bot")
        cmd_row = conn.execute("SELECT status FROM commands WHERE id = ?", (command_id,)).fetchone()
        audit_count = conn.execute("SELECT COUNT(*) FROM audit_log WHERE command_id = ?", (command_id,)).fetchone()[0]
    finally:
        conn.close()

    assert cmd_row[0] == "SUCCEEDED"
    assert audit_count >= 2


def test_strategy_params_api_reload_updates_snapshot_meta(client: TestClient):
    _login(client, "admin", "admin-pass")

    update_res = client.put(
        "/strategy-params/ema_vwap/normal",
        json={"params": {"vwap_atr_tolerance": 0.01}},
    )
    assert update_res.status_code == 200

    conn = connect()
    try:
        init_db(conn)
        run_cycle_once(conn, pairs=["EUR_USD"], now_utc=datetime.now(timezone.utc), handled_by="itest-bot")
        row = conn.execute(
            "SELECT details_json FROM gate_snapshots WHERE pair = 'EUR_USD' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    import json

    details = json.loads(row[0])
    params_meta = details.get("strategy_params")
    assert params_meta is not None
    assert params_meta["strategy_name"] == "ema_vwap"
    assert params_meta["params"]["vwap_atr_tolerance"] == 0.01
