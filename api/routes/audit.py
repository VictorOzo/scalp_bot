from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, require_viewer

router = APIRouter(tags=["audit"])


@router.get("/audit")
def list_audit(
    limit: int = Query(default=200, ge=1, le=2000),
    actor: str | None = None,
    action: str | None = None,
    since_ts_utc: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
    _=Depends(require_viewer),
) -> list[dict[str, object]]:
    where: list[str] = []
    params: list[object] = []

    if actor:
        where.append("actor = ?")
        params.append(actor)

    if action:
        where.append("action = ?")
        params.append(action)

    if since_ts_utc:
        try:
            datetime.fromisoformat(since_ts_utc.replace("Z", "+00:00"))
        except Exception:
            since_ts_utc = None
        if since_ts_utc:
            where.append("ts_utc >= ?")
            params.append(since_ts_utc)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    rows = conn.execute(
        f"""
        SELECT id, ts_utc, actor, action, command_id, details_json
        FROM audit_log
        {where_clause}
        ORDER BY ts_utc DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    ).fetchall()

    return [
        {
            "id": int(r[0]),
            "ts_utc": r[1],
            "actor": r[2],
            "action": r[3],
            "command_id": r[4],
            "details_json": r[5],
        }
        for r in rows
    ]