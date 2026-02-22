from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, require_viewer

router = APIRouter(tags=["trades"])


def _query_trades(
    conn: sqlite3.Connection,
    *,
    pair: str | None,
    from_ts: str | None,
    to_ts: str | None,
    side: str | None,
    mode: str | None,
    command_id: int | None,
    limit: int,
    cursor: int | None,
) -> tuple[list[dict[str, object]], int | None]:
    where: list[str] = []
    params: list[object] = []

    if pair:
        where.append("pair = ?")
        params.append(pair)

    # Your schema uses ts_utc as the trade timestamp
    if from_ts:
        where.append("ts_utc >= ?")
        params.append(from_ts)
    if to_ts:
        where.append("ts_utc <= ?")
        params.append(to_ts)

    # Your schema uses side (not direction)
    if side:
        where.append("side = ?")
        params.append(side.upper())

    # Your schema has a dedicated mode column
    if mode:
        where.append("mode = ?")
        params.append(mode.upper())

    # Your schema has a dedicated command_id column
    if command_id is not None:
        where.append("command_id = ?")
        params.append(command_id)

    if cursor is not None:
        where.append("id < ?")
        params.append(cursor)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    rows = conn.execute(
        f"""
        SELECT
            id,
            ts_utc,
            pair,
            side,
            units,
            price,
            mode,
            position_id,
            command_id,
            meta_json
        FROM trades
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
        """,
        tuple([*params, limit]),
    ).fetchall()

    items: list[dict[str, object]] = []
    next_cursor: int | None = None

    for row in rows:
        meta = json.loads(row[9]) if row[9] else {}
        items.append(
            {
                "id": int(row[0]),
                "opened_ts_utc": row[1],  # keep API stable; maps to ts_utc
                "closed_ts_utc": None,  # this schema doesn't store close time
                "pair": row[2],
                "side": row[3],
                "units": float(row[4]) if row[4] is not None else None,
                "entry_price": float(row[5]) if row[5] is not None else None,  # maps to price
                "exit_price": None,
                "result": None,
                "mode": (row[6] or meta.get("mode") or "PAPER"),
                "position_id": int(row[7]) if row[7] is not None else None,
                "command_id": int(row[8]) if row[8] is not None else meta.get("command_id"),
            }
        )

    if items:
        next_cursor = int(items[-1]["id"])
    return items, next_cursor


@router.get("/trades")
def list_trades(
    pair: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    side: str | None = None,
    mode: str | None = None,
    command_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
    _=Depends(require_viewer),
) -> dict[str, object]:
    items, next_cursor = _query_trades(
        conn,
        pair=pair,
        from_ts=from_ts,
        to_ts=to_ts,
        side=side,
        mode=mode,
        command_id=command_id,
        limit=limit,
        cursor=cursor,
    )
    return {"items": items, "next_cursor": next_cursor}