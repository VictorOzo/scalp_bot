from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest

pytest.importorskip("fastapi")
openpyxl = pytest.importorskip("openpyxl")
from fastapi.testclient import TestClient

from api.app import app
from api.auth import ensure_user
from execution.trade_store import TradeStore
from storage.db import connect, init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_exports.sqlite"
    monkeypatch.setenv("SCALP_BOT_DB_PATH", str(db_path))
    conn = connect(db_path)
    init_db(conn)
    ensure_user(conn, username="viewer", password="viewer-pass", role="viewer")
    TradeStore(db_path).init_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO trades (time_open_utc,time_close_utc,pair,strategy,direction,units,entry_price,exit_price,sl_price,tp_price,result,pnl_pips,pnl_quote,meta_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, now, "EUR_USD", "ema_vwap", "BUY", 1000, 1.1, 1.101, 1.099, 1.102, "TP", 10.0, 1.0, '{"mode":"PAPER"}'),
    )
    conn.commit()
    conn.close()
    with TestClient(app) as test_client:
        login = test_client.post("/auth/login", json={"username": "viewer", "password": "viewer-pass"})
        assert login.status_code == 200
        yield test_client


def test_export_trades_xlsx_returns_valid_workbook(client: TestClient) -> None:
    res = client.get("/exports/trades.xlsx")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(res.content) > 0

    wb = openpyxl.load_workbook(BytesIO(res.content))
    ws = wb["trades"]
    assert ws["A1"].value == "id"
    assert ws.max_row >= 2
