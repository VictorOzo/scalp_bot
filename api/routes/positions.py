from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, require_viewer

router = APIRouter(tags=["positions"])


@router.get("/positions")
def list_positions(
    status: str = Query(default="OPEN"),
    pair: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
    _=Depends(require_viewer),
) -> list[dict[str, object]]:
    normalized = status.upper()
    if normalized not in {"OPEN", "CLOSED"}:
        normalized = "OPEN"

    where = ["is_open = ?"]
    params: list[object] = [1 if normalized == "OPEN" else 0]
    if pair:
        where.append("pair = ?")
        params.append(pair)

    rows = conn.execute(
        """
        SELECT pair,direction,units,entry_price,time_open_utc,is_open
        FROM positions
        WHERE {where_clause}
        ORDER BY time_open_utc DESC
        """.format(where_clause=" AND ".join(where)),
        tuple(params),
    ).fetchall()

    return [
        {
            "id": f"{row[0]}:{row[4]}",
            "pair": row[0],
            "side": row[1],
            "units": int(row[2]),
            "entry_price": float(row[3]),
            "opened_ts_utc": row[4],
            "status": "OPEN" if int(row[5]) == 1 else "CLOSED",
        }
        for row in rows
    ]
