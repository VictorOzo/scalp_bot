from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import app
from api.auth import ensure_user
from execution.trade_store import TradeStore
from storage.db import connect, init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_trades.sqlite"
    monkeypatch.setenv("SCALP_BOT_DB_PATH", str(db_path))
    conn = connect(db_path)
    init_db(conn)
    ensure_user(conn, username="admin", password="admin-pass", role="admin")
    TradeStore(db_path).init_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO trades (time_open_utc,time_close_utc,pair,strategy,direction,units,entry_price,exit_price,sl_price,tp_price,result,pnl_pips,pnl_quote,meta_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, now, "EUR_USD", "ema_vwap", "BUY", 1000, 1.1, 1.101, 1.099, 1.102, "TP", 10.0, 1.0, '{"mode":"PAPER","command_id":10}'),
    )
    conn.execute(
        "INSERT INTO trades (time_open_utc,time_close_utc,pair,strategy,direction,units,entry_price,exit_price,sl_price,tp_price,result,pnl_pips,pnl_quote,meta_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, now, "GBP_USD", "ema_vwap", "SELL", 1000, 1.2, 1.199, 1.201, 1.198, "TP", 10.0, 1.0, '{"mode":"PAPER","command_id":11}'),
    )
    conn.commit()
    conn.close()
    with TestClient(app) as test_client:
        login = test_client.post("/auth/login", json={"username": "admin", "password": "admin-pass"})
        assert login.status_code == 200
        yield test_client


def test_trades_filter_and_cursor(client: TestClient) -> None:
    res = client.get("/trades", params={"pair": "EUR_USD", "limit": 1})
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["pair"] == "EUR_USD"
    cursor = body["next_cursor"]

    res2 = client.get("/trades", params={"cursor": cursor, "limit": 1})
    assert res2.status_code == 200


def test_trades_date_filter(client: TestClient) -> None:
    from_ts = "2000-01-01T00:00:00+00:00"
    to_ts = "2100-01-01T00:00:00+00:00"
    res = client.get("/trades", params={"from_ts": from_ts, "to_ts": to_ts, "side": "BUY"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert all(item["side"] == "BUY" for item in items)
