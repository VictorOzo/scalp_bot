from __future__ import annotations

import os

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import app
from api.auth import ensure_user
from storage.db import connect, init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_auth.sqlite"
    monkeypatch.setenv("SCALP_BOT_DB_PATH", str(db_path))
    conn = connect(db_path)
    init_db(conn)
    ensure_user(conn, username="admin", password="admin-pass", role="admin")
    ensure_user(conn, username="viewer", password="viewer-pass", role="viewer")
    conn.close()
    with TestClient(app) as test_client:
        yield test_client


def test_protected_route_requires_cookie(client: TestClient) -> None:
    res = client.get("/status")
    assert res.status_code == 401


def test_login_sets_http_only_cookie(client: TestClient) -> None:
    res = client.post("/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert res.status_code == 200
    cookie = res.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie


def test_viewer_cannot_post_commands(client: TestClient) -> None:
    login = client.post("/auth/login", json={"username": "viewer", "password": "viewer-pass"})
    assert login.status_code == 200
    res = client.post("/commands", json={"type": "PAUSE_ALL", "payload": {}})
    assert res.status_code == 403


def test_admin_can_post_commands(client: TestClient) -> None:
    login = client.post("/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert login.status_code == 200
    res = client.post("/commands", json={"type": "PAUSE_ALL", "payload": {}})
    assert res.status_code == 200
    assert res.json()["status"] == "PENDING"
