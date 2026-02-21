from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from execution.control_state import PAUSE_COMMANDS, apply_pause_command
from storage.commands import fetch_next_pending, mark_command_done, mark_command_failed, mark_command_running
from storage.db import write_gate_snapshot, write_heartbeat


def _load_latest_paused_pairs(conn: sqlite3.Connection) -> set[str]:
    row = conn.execute("SELECT paused_pairs_json FROM bot_status ORDER BY id DESC LIMIT 1").fetchone()
    if row is None or row[0] is None:
        return set()
    return set(json.loads(row[0]))


def run_cycle_once(conn: sqlite3.Connection, pairs: list[str], now_utc: datetime, offline: bool = True) -> None:
    """Run one offline-safe control cycle: process one command and write snapshots."""
    if not offline:
        raise ValueError("run_cycle_once supports offline mode only")

    paused_pairs = _load_latest_paused_pairs(conn)
    command_id = None

    command = fetch_next_pending(conn)
    if command is not None:
        command_id = int(command["id"])
        mark_command_running(conn, command_id)
        if command["type"] in PAUSE_COMMANDS:
            paused_pairs = apply_pause_command(paused_pairs, command)
            mark_command_done(
                conn,
                command_id,
                result={"paused_pairs": sorted(paused_pairs), "type": command["type"]},
            )
        else:
            mark_command_failed(conn, command_id, error=f"Command not implemented in phase D2: {command['type']}")

    for pair in pairs:
        if pair in paused_pairs:
            write_gate_snapshot(
                conn,
                ts_utc=now_utc.isoformat(),
                pair=pair,
                strategy="phase2_test",
                session_ok=False,
                spread_ok=False,
                news_ok=False,
                open_pos_ok=False,
                daily_ok=False,
                enemy_ok=False,
                final_signal="HOLD",
                reason="paused",
                details={"paused_by": "command", "command_id": command_id},
            )
        else:
            write_gate_snapshot(
                conn,
                ts_utc=now_utc.isoformat(),
                pair=pair,
                strategy="phase2_test",
                session_ok=True,
                spread_ok=True,
                news_ok=True,
                open_pos_ok=True,
                daily_ok=True,
                enemy_ok=True,
                final_signal="HOLD",
                reason="cycle_once",
                details={"offline": True},
            )

    write_heartbeat(
        conn,
        mode="OFFLINE",
        version=None,
        uptime_s=None,
        last_cycle_ts_utc=now_utc.isoformat(),
        paused_pairs=sorted(paused_pairs),
        meta={"tool": "tests.tools._cycle_once"},
    )
