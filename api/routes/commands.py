from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import AuthenticatedUser
from api.deps import get_db, require_admin
from storage.commands import ALLOWED_COMMAND_TYPES, enqueue_command

router = APIRouter(tags=["commands"])


class CommandCreateRequest(BaseModel):
    type: str
    payload: dict[str, object] | None = None
    idempotency_key: str | None = None


@router.post("/commands")
def post_command(
    payload: CommandCreateRequest,
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    if payload.type not in ALLOWED_COMMAND_TYPES:
        raise HTTPException(status_code=400, detail="Invalid command type")

    command_id = enqueue_command(
        conn,
        actor=user.username,
        type=payload.type,
        payload=payload.payload,
        idempotency_key=payload.idempotency_key,
    )
    row = conn.execute(
        "SELECT id, status, type, created_ts_utc FROM commands WHERE id = ?",
        (command_id,),
    ).fetchone()
    return {"id": int(row[0]), "status": row[1], "type": row[2], "created_ts_utc": row[3]}
