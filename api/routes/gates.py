from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, require_viewer

router = APIRouter(tags=["gates"])


@router.get("/gates")
def list_gates(
    pair: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_db),
    _=Depends(require_viewer),
) -> list[dict[str, object]]:
    params: list[object]
    sql = (
        "SELECT ts_utc,pair,final_signal,reason,details_json FROM gate_snapshots "
        "{where_clause} ORDER BY id DESC LIMIT ?"
    )
    if pair:
        params = [pair, limit]
        where_clause = "WHERE pair = ?"
    else:
        params = [limit]
        where_clause = ""

    rows = conn.execute(sql.format(where_clause=where_clause), tuple(params)).fetchall()
    out: list[dict[str, object]] = []
    for row in rows:
        details = json.loads(row[4]) if row[4] else {}
        reason = row[3] if row[3] else details.get("reason")
        out.append(
            {
                "ts_utc": row[0],
                "pair": row[1],
                "allowed": str(row[2]).upper() != "HOLD",
                "reasons": [reason] if reason else [],
                "snapshot_json": details,
            }
        )
    return out
