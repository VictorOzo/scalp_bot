from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, require_viewer
from config.settings import LIVE_TRADING_ENABLED

router = APIRouter(tags=["status"])


@router.get("/status")
def get_status(conn: sqlite3.Connection = Depends(get_db), _=Depends(require_viewer)) -> dict[str, object]:
    heartbeat = conn.execute(
        "SELECT mode, last_cycle_ts_utc, meta_json FROM bot_status ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if heartbeat is None:
        return {
            "heartbeat": False,
            "mode": "LIVE" if LIVE_TRADING_ENABLED else "PAPER",
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "last_cycle_ts_utc": None,
            "meta": None,
        }
    return {
        "heartbeat": True,
        "mode": str(heartbeat[0]),
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "last_cycle_ts_utc": heartbeat[1],
        "meta": json.loads(heartbeat[2]) if heartbeat[2] else None,
    }
