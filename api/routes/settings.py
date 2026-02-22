from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedUser
from api.deps import get_db, require_admin
from storage.db import utc_now_iso

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings(conn: sqlite3.Connection = Depends(get_db), user: AuthenticatedUser = Depends(require_admin)) -> dict[str, object]:
    rows = conn.execute("SELECT key, value_json FROM app_settings ORDER BY key").fetchall()
    return {row[0]: json.loads(row[1]) for row in rows}


@router.put("/settings")
def put_settings(
    payload: dict[str, Any],
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    for key, value in payload.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_ts_utc, updated_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_ts_utc = excluded.updated_ts_utc,
                updated_by = excluded.updated_by
            """,
            (key, json.dumps(value, sort_keys=True), utc_now_iso(), user.username),
        )
    conn.execute(
        "INSERT INTO audit_log (ts_utc, actor, action, command_id, details_json) VALUES (?, ?, ?, NULL, ?)",
        (utc_now_iso(), user.username, "SETTINGS_UPDATED", json.dumps(payload, sort_keys=True)),
    )
    conn.commit()
    return {"updated": sorted(payload.keys())}
