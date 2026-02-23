from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import AuthenticatedUser
from api.deps import get_db, require_admin
from api.strategy_params_validation import validate_params, validate_strategy_and_profile
from storage.commands import enqueue_command
from storage.strategy_params import PROFILES, list_strategy_params, set_active_profile, upsert_profile_params

router = APIRouter(tags=["strategy_params"])


class StrategyParamsUpdateRequest(BaseModel):
    params: dict[str, Any]


class StrategyProfileSwitchRequest(BaseModel):
    profile: str


@router.get("/strategy-params/{strategy_name}")
def get_strategy_params(
    strategy_name: str,
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return list_strategy_params(conn, strategy_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/strategy-params/{strategy_name}/{profile}")
def put_strategy_params(
    strategy_name: str,
    profile: str,
    payload: StrategyParamsUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    errors = validate_strategy_and_profile(strategy_name, profile)
    errors.extend(validate_params(strategy_name, payload.params))
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    params = {key: float(value) for key, value in payload.params.items()}
    upsert_profile_params(
        conn,
        strategy_name=strategy_name,
        profile=profile,
        params=params,
        updated_by=user.username,
    )
    command_id = enqueue_command(conn, actor=user.username, type="RELOAD_PARAMS")
    return {
        "strategy_name": strategy_name,
        "profile": profile,
        "updated_keys": sorted(params.keys()),
        "reload_command_id": command_id,
    }


@router.post("/strategy-params/{strategy_name}/active-profile")
def post_strategy_params_active_profile(
    strategy_name: str,
    payload: StrategyProfileSwitchRequest,
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    errors = validate_strategy_and_profile(strategy_name, payload.profile)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    try:
        set_active_profile(conn, strategy_name=strategy_name, profile=payload.profile, updated_by=user.username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    command_id = enqueue_command(conn, actor=user.username, type="RELOAD_PARAMS")
    return {
        "strategy_name": strategy_name,
        "active_profile": payload.profile,
        "available_profiles": list(PROFILES),
        "reload_command_id": command_id,
    }


@router.post("/strategy-params/reload")
def post_strategy_params_reload(
    conn: sqlite3.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_admin),
) -> dict[str, Any]:
    command_id = enqueue_command(conn, actor=user.username, type="RELOAD_PARAMS")
    return {"command_id": command_id, "type": "RELOAD_PARAMS"}
