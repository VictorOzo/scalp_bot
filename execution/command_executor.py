"""DB-driven command execution for control-plane actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import traceback
from typing import Any, Callable

from config.settings import LIVE_TRADING_ENABLED
from execution.alerting import get_alert_service
from execution.alerts import AlertEvent
from execution.control_state import PAUSE_COMMANDS, apply_pause_command
from execution.trade_store import TradeStore
from storage.commands import (
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCEEDED,
    claim_next_pending,
    mark_command_finished,
)

LiveCloseFn = Callable[[str], dict[str, Any] | None]


def _audit(conn, *, actor: str, action: str, command_id: int, details: dict[str, Any] | None) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts_utc, actor, action, command_id, details_json) VALUES (datetime('now'), ?, ?, ?, ?)",
        (actor, action, command_id, json.dumps(details, sort_keys=True) if details is not None else None),
    )
    conn.commit()


def _close_paper_pair(store: TradeStore, pair: str, command_id: int, actor: str, conn) -> tuple[str, dict[str, Any]]:
    position = store.get_open_position(pair)
    if position is None:
        result = {"pair": pair, "reason": "position already closed", "mode": "PAPER"}
        _audit(conn, actor=actor, action="POSITION_CLOSE_SKIPPED", command_id=command_id, details=result)
        return STATUS_SKIPPED, result

    exit_price = float(position["entry_price"])
    store.close_position(pair, exit_price=exit_price, result="MANUAL_CLOSE", meta_json={"command_id": command_id})
    result = {"pair": pair, "closed": True, "mode": "PAPER", "exit_price": exit_price}
    _audit(conn, actor=actor, action="POSITION_CLOSED", command_id=command_id, details=result)
    return STATUS_SUCCEEDED, result


def _close_live_pair(pair: str, *, command_id: int, actor: str, conn, live_close_fn: LiveCloseFn | None) -> tuple[str, dict[str, Any]]:
    if not LIVE_TRADING_ENABLED:
        result = {"pair": pair, "mode": "LIVE", "reason": "LIVE trading disabled"}
        _audit(conn, actor=actor, action="LIVE_CLOSE_SKIPPED", command_id=command_id, details=result)
        return STATUS_SKIPPED, result

    if live_close_fn is None:
        raise RuntimeError("LIVE close requested but no live_close_fn provided")

    payload = live_close_fn(pair) or {}
    result = {"pair": pair, "mode": "LIVE", "broker": payload}
    _audit(conn, actor=actor, action="BROKER_CLOSE_CALLED", command_id=command_id, details=result)
    return STATUS_SUCCEEDED, result


def _handle_close_pair(
    conn,
    *,
    cmd: dict[str, Any],
    actor: str,
    store: TradeStore,
    live_close_fn: LiveCloseFn | None,
) -> tuple[str, dict[str, Any]]:
    payload = cmd.get("payload") or {}
    pair = payload.get("pair")
    if not pair:
        return STATUS_FAILED, {"error": "pair is required"}

    mode = str(payload.get("mode") or "PAPER").upper()
    if mode == "LIVE":
        return _close_live_pair(pair, command_id=int(cmd["id"]), actor=actor, conn=conn, live_close_fn=live_close_fn)
    return _close_paper_pair(store, pair, command_id=int(cmd["id"]), actor=actor, conn=conn)


def _handle_close_all(
    conn,
    *,
    cmd: dict[str, Any],
    actor: str,
    store: TradeStore,
    live_close_fn: LiveCloseFn | None,
) -> tuple[str, dict[str, Any]]:
    payload = cmd.get("payload") or {}
    modes = payload.get("modes") or ["PAPER", "LIVE"]
    normalized = {str(item).upper() for item in modes}
    results: list[dict[str, Any]] = []
    status = STATUS_SUCCEEDED

    if "PAPER" in normalized:
        for position in store.list_open_positions():
            pair = str(position["pair"])
            pair_status, result = _close_paper_pair(store, pair, command_id=int(cmd["id"]), actor=actor, conn=conn)
            results.append(result)
            if pair_status == STATUS_SKIPPED and status == STATUS_SUCCEEDED:
                status = STATUS_SKIPPED

    if "LIVE" in normalized:
        live_pairs = payload.get("pairs") or []
        for pair in live_pairs:
            pair_status, result = _close_live_pair(str(pair), command_id=int(cmd["id"]), actor=actor, conn=conn, live_close_fn=live_close_fn)
            results.append(result)
            if pair_status == STATUS_FAILED:
                status = STATUS_FAILED
            elif pair_status == STATUS_SKIPPED and status == STATUS_SUCCEEDED:
                status = STATUS_SKIPPED

    _audit(conn, actor=actor, action="CLOSE_ALL_SUMMARY", command_id=int(cmd["id"]), details={"results": results})
    return status, {"results": results}


def process_next_command(
    conn,
    *,
    paused_pairs: set[str],
    handled_by: str,
    trade_store: TradeStore | None = None,
    live_close_fn: LiveCloseFn | None = None,
    reload_params_fn: Callable[[], None] | None = None,
) -> tuple[set[str], dict[str, Any] | None]:
    cmd = claim_next_pending(conn, handled_by=handled_by)
    if cmd is None:
        return paused_pairs, None

    store = trade_store or TradeStore()
    command_id = int(cmd["id"])
    alert_service = get_alert_service()

    try:
        if cmd["type"] in PAUSE_COMMANDS:
            updated = apply_pause_command(paused_pairs, cmd)
            result = {"paused_pairs": sorted(updated), "type": cmd["type"]}
            mark_command_finished(conn, command_id, status=STATUS_SUCCEEDED, result=result, actor=handled_by)
            if cmd["type"] in {"PAUSE_ALL", "RESUME_ALL"}:
                alert_service.send(
                    AlertEvent.KILL_SWITCH,
                    {
                        "enabled": cmd["type"] == "PAUSE_ALL",
                        "source": "command_executor",
                        "reason": cmd["type"],
                        "pairs_closed": 0,
                        "time_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )
            return updated, {"id": command_id, "status": STATUS_SUCCEEDED, "result": result}

        if cmd["type"] == "CLOSE_PAIR":
            status, result = _handle_close_pair(conn, cmd=cmd, actor=handled_by, store=store, live_close_fn=live_close_fn)
            mark_command_finished(conn, command_id, status=status, result=result, actor=handled_by)
            if status == STATUS_SUCCEEDED and result.get("closed"):
                alert_service.send(
                    AlertEvent.TRADE_CLOSE,
                    {
                        "pair": result.get("pair"),
                        "result": "MANUAL_CLOSE",
                        "exit_price": result.get("exit_price"),
                        "time_utc": cmd.get("finished_ts_utc") or cmd.get("created_ts_utc"),
                    },
                )
            return paused_pairs, {"id": command_id, "status": status, "result": result}

        if cmd["type"] == "CLOSE_ALL":
            status, result = _handle_close_all(conn, cmd=cmd, actor=handled_by, store=store, live_close_fn=live_close_fn)
            mark_command_finished(conn, command_id, status=status, result=result, actor=handled_by)
            alert_service.send(
                AlertEvent.KILL_SWITCH,
                {
                    "enabled": True,
                    "source": "command_executor",
                    "reason": "CLOSE_ALL",
                    "pairs_closed": len(result.get("results", [])),
                    "time_utc": cmd.get("created_ts_utc"),
                },
            )
            return paused_pairs, {"id": command_id, "status": status, "result": result}

        if cmd["type"] == "RELOAD_PARAMS":
            if reload_params_fn is None:
                result = {"reloaded": False, "reason": "reload handler not configured"}
                mark_command_finished(conn, command_id, status=STATUS_SKIPPED, result=result, actor=handled_by)
                return paused_pairs, {"id": command_id, "status": STATUS_SKIPPED, "result": result}

            reload_params_fn()
            result = {"reloaded": True}
            mark_command_finished(conn, command_id, status=STATUS_SUCCEEDED, result=result, actor=handled_by)
            return paused_pairs, {"id": command_id, "status": STATUS_SUCCEEDED, "result": result}

        result = {"error": f"unsupported command type: {cmd['type']}"}
        mark_command_finished(conn, command_id, status=STATUS_FAILED, result=result, actor=handled_by)
        return paused_pairs, {"id": command_id, "status": STATUS_FAILED, "result": result}
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc), "stack": traceback.format_exc()}
        mark_command_finished(conn, command_id, status=STATUS_FAILED, result=result, actor=handled_by)
        return paused_pairs, {"id": command_id, "status": STATUS_FAILED, "result": result}
