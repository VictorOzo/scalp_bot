from __future__ import annotations

from io import BytesIO
import sqlite3

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font

from api.deps import get_db, require_viewer
from api.routes.trades import _query_trades

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/trades.xlsx")
def export_trades_xlsx(
    pair: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    side: str | None = None,
    mode: str | None = None,
    command_id: int | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_db),
    _=Depends(require_viewer),
) -> StreamingResponse:
    items, _ = _query_trades(
        conn,
        pair=pair,
        from_ts=from_ts,
        to_ts=to_ts,
        side=side,
        mode=mode,
        command_id=command_id,
        limit=limit,
        cursor=None,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "trades"
    headers = ["id", "opened_ts_utc", "closed_ts_utc", "pair", "side", "units", "entry_price", "exit_price", "result", "mode", "command_id"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for item in items:
        ws.append([item.get(key) for key in headers])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="trades.xlsx"'},
    )
