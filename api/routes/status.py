from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, require_viewer
from config.settings import LIVE_TRADING_ENABLED
from execution.runtime_ops import is_heartbeat_stale, stale_threshold_seconds

router = APIRouter(tags=["status"])


@router.get("/status")
def get_status(conn: sqlite3.Connection = Depends(get_db), _=Depends(require_viewer)) -> dict[str, object]:
    heartbeat = conn.execute(
        "SELECT mode, last_cycle_ts_utc, meta_json FROM bot_status ORDER BY id DESC LIMIT 1"
    ).fetchone()
    runtime = conn.execute(
        "SELECT last_heartbeat_at, last_restart_at, startup_time_utc, version FROM bot_runtime WHERE id=1"
    ).fetchone()

    last_heartbeat_at = runtime[0] if runtime else None
    threshold = stale_threshold_seconds()
    stale = is_heartbeat_stale(last_heartbeat_at=last_heartbeat_at, threshold_seconds=threshold)

    if heartbeat is None:
        return {
            "heartbeat": False,
            "mode": "LIVE" if LIVE_TRADING_ENABLED else "PAPER",
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "last_cycle_ts_utc": None,
            "meta": None,
            "last_heartbeat_at": last_heartbeat_at,
            "is_stale": stale,
            "stale_threshold_seconds": threshold,
            "last_restart_at": runtime[1] if runtime else None,
            "uptime_start_utc": runtime[2] if runtime else None,
            "version": runtime[3] if runtime else None,
        }
    return {
        "heartbeat": True,
        "mode": str(heartbeat[0]),
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "last_cycle_ts_utc": heartbeat[1],
        "meta": json.loads(heartbeat[2]) if heartbeat[2] else None,
        "last_heartbeat_at": last_heartbeat_at,
        "is_stale": stale,
        "stale_threshold_seconds": threshold,
        "last_restart_at": runtime[1] if runtime else None,
        "uptime_start_utc": runtime[2] if runtime else None,
        "version": runtime[3] if runtime else None,
    }


@router.get("/bot/status")
def get_bot_status(conn: sqlite3.Connection = Depends(get_db), _=Depends(require_viewer)) -> dict[str, object]:
    runtime = conn.execute(
        "SELECT last_heartbeat_at, last_restart_at, startup_time_utc, version FROM bot_runtime WHERE id=1"
    ).fetchone()
    threshold = stale_threshold_seconds()
    last_heartbeat_at = runtime[0] if runtime else None
    return {
        "last_heartbeat_at": last_heartbeat_at,
        "is_stale": is_heartbeat_stale(last_heartbeat_at=last_heartbeat_at, threshold_seconds=threshold),
        "stale_threshold_seconds": threshold,
        "last_restart_at": runtime[1] if runtime else None,
        "uptime_start_utc": runtime[2] if runtime else None,
        "version": runtime[3] if runtime else None,
    }
