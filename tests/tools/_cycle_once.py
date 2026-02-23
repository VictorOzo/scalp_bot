from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Callable

from config.settings import COMMAND_RUNNING_TIMEOUT_SEC
from execution.command_executor import process_next_command
from execution.trade_store import TradeStore
from storage.commands import fail_stale_running_commands
from storage.db import get_db_path, write_gate_snapshot, write_heartbeat
from storage.strategy_params import get_strategy_params_service


def _load_latest_paused_pairs(conn: sqlite3.Connection) -> set[str]:
    row = conn.execute("SELECT paused_pairs_json FROM bot_status ORDER BY id DESC LIMIT 1").fetchone()
    if row is None or row[0] is None:
        return set()
    return set(json.loads(row[0]))


def run_cycle_once(
    conn: sqlite3.Connection,
    pairs: list[str],
    now_utc: datetime,
    offline: bool = True,
    strategy_eval: Callable[[str], None] | None = None,
    handled_by: str = "cycle_once",
) -> None:
    """Run one offline-safe control cycle: process one command and write snapshots."""
    if not offline:
        raise ValueError("run_cycle_once supports offline mode only")

    paused_pairs = _load_latest_paused_pairs(conn)
    params_service = get_strategy_params_service(get_db_path())
    fail_stale_running_commands(conn, timeout_sec=COMMAND_RUNNING_TIMEOUT_SEC, handled_by=handled_by)
    db_row = conn.execute("PRAGMA database_list").fetchone()
    trade_store = TradeStore(db_row[2]) if db_row and db_row[2] else TradeStore()

    paused_pairs, command_result = process_next_command(
        conn,
        paused_pairs=paused_pairs,
        handled_by=handled_by,
        trade_store=trade_store,
        reload_params_fn=params_service.reload,
    )
    command_id = None if command_result is None else int(command_result["id"])

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
                details={"paused": True, "pair": pair, "paused_by": "command", "command_id": command_id},
            )
        else:
            if strategy_eval is not None:
                strategy_eval(pair)
            strategy_name = "phase2_test"
            try:
                strategy_name = {"EUR_USD": "ema_vwap", "USD_JPY": "vwap_rsi", "GBP_USD": "bb_breakout"}.get(pair, strategy_name)
                snapshot = params_service.get(strategy_name)
                strategy_params_meta = {
                    "strategy_name": snapshot.strategy_name,
                    "profile": snapshot.profile,
                    "params": snapshot.params,
                }
            except KeyError:
                strategy_params_meta = None

            write_gate_snapshot(
                conn,
                ts_utc=now_utc.isoformat(),
                pair=pair,
                strategy=strategy_name,
                session_ok=True,
                spread_ok=True,
                news_ok=True,
                open_pos_ok=True,
                daily_ok=True,
                enemy_ok=True,
                final_signal="HOLD",
                reason="cycle_once",
                details={"offline": True, "strategy_params": strategy_params_meta},
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
