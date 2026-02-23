from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storage.db import utc_now_iso

PROFILES = ("conservative", "normal", "aggressive")

DEFAULT_PRESETS: dict[str, dict[str, dict[str, float]]] = {
    "ema_vwap": {
        "conservative": {"vwap_atr_tolerance": 0.1},
        "normal": {"vwap_atr_tolerance": 0.2},
        "aggressive": {"vwap_atr_tolerance": 0.3},
    },
    "vwap_rsi": {
        "conservative": {"rsi_buy_max": 20.0, "rsi_sell_min": 80.0, "vwap_atr_tolerance": 0.05, "rsi_period": 3.0},
        "normal": {"rsi_buy_max": 25.0, "rsi_sell_min": 75.0, "vwap_atr_tolerance": 0.1, "rsi_period": 3.0},
        "aggressive": {"rsi_buy_max": 30.0, "rsi_sell_min": 70.0, "vwap_atr_tolerance": 0.15, "rsi_period": 3.0},
    },
    "bb_breakout": {
        "conservative": {"volume_spike_mult": 1.4, "squeeze_percentile": 25.0, "squeeze_expand_mult": 1.05},
        "normal": {"volume_spike_mult": 1.2, "squeeze_percentile": 35.0, "squeeze_expand_mult": 1.02},
        "aggressive": {"volume_spike_mult": 1.05, "squeeze_percentile": 45.0, "squeeze_expand_mult": 1.0},
    },
}


@dataclass(frozen=True)
class StrategyParamsSnapshot:
    strategy_name: str
    profile: str
    params: dict[str, float]


def _dump(value: dict[str, float]) -> str:
    return json.dumps(value, sort_keys=True)


def _load(value: str) -> dict[str, float]:
    raw = json.loads(value)
    return {str(k): float(v) for k, v in raw.items()}


def seed_defaults(conn: sqlite3.Connection, *, updated_by: str = "system") -> None:
    for strategy_name, profiles in DEFAULT_PRESETS.items():
        for profile_name, params in profiles.items():
            conn.execute(
                """
                INSERT INTO strategy_params (strategy_name, profile, params_json, is_active, updated_ts_utc, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(strategy_name, profile) DO NOTHING
                """,
                (
                    strategy_name,
                    profile_name,
                    _dump(params),
                    1 if profile_name == "normal" else 0,
                    utc_now_iso(),
                    updated_by,
                ),
            )

        active_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_params WHERE strategy_name = ? AND is_active = 1",
            (strategy_name,),
        ).fetchone()[0]
        if int(active_count) == 0:
            conn.execute(
                "UPDATE strategy_params SET is_active = CASE WHEN profile = 'normal' THEN 1 ELSE 0 END WHERE strategy_name = ?",
                (strategy_name,),
            )
    conn.commit()


def list_strategy_params(conn: sqlite3.Connection, strategy_name: str) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT strategy_name, profile, params_json, is_active FROM strategy_params WHERE strategy_name = ? ORDER BY profile",
        (strategy_name,),
    ).fetchall()
    if not rows:
        raise KeyError(strategy_name)

    profiles = {str(row[1]): _load(str(row[2])) for row in rows}
    active_profile = next((str(row[1]) for row in rows if int(row[3]) == 1), "normal")
    return {"strategy_name": strategy_name, "active_profile": active_profile, "profiles": profiles}


def upsert_profile_params(
    conn: sqlite3.Connection,
    *,
    strategy_name: str,
    profile: str,
    params: dict[str, float],
    updated_by: str,
) -> None:
    conn.execute(
        """
        INSERT INTO strategy_params (strategy_name, profile, params_json, is_active, updated_ts_utc, updated_by)
        VALUES (?, ?, ?, 0, ?, ?)
        ON CONFLICT(strategy_name, profile) DO UPDATE SET
            params_json = excluded.params_json,
            updated_ts_utc = excluded.updated_ts_utc,
            updated_by = excluded.updated_by
        """,
        (strategy_name, profile, _dump(params), utc_now_iso(), updated_by),
    )
    conn.commit()


def set_active_profile(conn: sqlite3.Connection, *, strategy_name: str, profile: str, updated_by: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM strategy_params WHERE strategy_name = ? AND profile = ?",
        (strategy_name, profile),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown profile {profile} for {strategy_name}")

    conn.execute(
        "UPDATE strategy_params SET is_active = CASE WHEN profile = ? THEN 1 ELSE 0 END, updated_ts_utc = ?, updated_by = ? WHERE strategy_name = ?",
        (profile, utc_now_iso(), updated_by, strategy_name),
    )
    conn.commit()


class StrategyParamsService:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._cache: dict[str, StrategyParamsSnapshot] = {}
        self.reload()

    def reload(self) -> None:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            try:
                seed_defaults(conn)
                rows = conn.execute(
                    "SELECT strategy_name, profile, params_json FROM strategy_params WHERE is_active = 1"
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        finally:
            conn.close()

        next_cache: dict[str, StrategyParamsSnapshot] = {}
        for row in rows:
            strategy_name = str(row["strategy_name"])
            next_cache[strategy_name] = StrategyParamsSnapshot(
                strategy_name=strategy_name,
                profile=str(row["profile"]),
                params=_load(str(row["params_json"])),
            )

        for strategy_name, profiles in DEFAULT_PRESETS.items():
            if strategy_name not in next_cache:
                next_cache[strategy_name] = StrategyParamsSnapshot(
                    strategy_name=strategy_name,
                    profile="normal",
                    params=dict(profiles["normal"]),
                )

        with self._lock:
            self._cache = next_cache

    def get(self, strategy_name: str) -> StrategyParamsSnapshot:
        with self._lock:
            cached = self._cache.get(strategy_name)
        if cached is not None:
            return cached

        profiles = DEFAULT_PRESETS.get(strategy_name)
        if profiles is None:
            raise KeyError(strategy_name)
        return StrategyParamsSnapshot(strategy_name=strategy_name, profile="normal", params=dict(profiles["normal"]))


_SERVICE_BY_PATH: dict[str, StrategyParamsService] = {}


def get_strategy_params_service(db_path: Path | str) -> StrategyParamsService:
    key = str(Path(db_path))
    service = _SERVICE_BY_PATH.get(key)
    if service is None:
        service = StrategyParamsService(key)
        _SERVICE_BY_PATH[key] = service
    return service
