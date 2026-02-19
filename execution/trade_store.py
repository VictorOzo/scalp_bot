"""SQLite-backed paper trading persistence with optional CSV export."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_ENV_VAR = "SCALP_BOT_DB_PATH"
DEFAULT_DB_PATH = Path("data/paper_trading.db")
SIGNALS_CSV_PATH = Path("data/signals_log.csv")
TRADES_CSV_PATH = Path("data/trades_log.csv")


class TradeStore:
    """Persistence abstraction for paper trading signals, trades, positions, and daily stats."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        resolved = db_path or os.getenv(DB_ENV_VAR) or DEFAULT_DB_PATH
        self.db_path = Path(resolved)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time_utc TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    session_gate INTEGER NOT NULL,
                    spread_gate INTEGER NOT NULL,
                    news_gate INTEGER NOT NULL,
                    open_pos_gate INTEGER NOT NULL,
                    daily_loss_gate INTEGER NOT NULL,
                    enemy_gate INTEGER NOT NULL,
                    signal TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    meta_json TEXT
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time_open_utc TEXT NOT NULL,
                    time_close_utc TEXT,
                    pair TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    sl_price REAL NOT NULL,
                    tp_price REAL NOT NULL,
                    result TEXT,
                    pnl_pips REAL,
                    pnl_quote REAL,
                    meta_json TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    pair TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    sl_price REAL NOT NULL,
                    tp_price REAL NOT NULL,
                    time_open_utc TEXT NOT NULL,
                    is_open INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date_utc TEXT PRIMARY KEY,
                    start_balance REAL NOT NULL,
                    current_balance REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    halted INTEGER NOT NULL
                );
                """
            )

    @staticmethod
    def _to_json(meta: dict[str, Any] | None) -> str:
        return json.dumps(meta or {}, sort_keys=True)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_csv(self, path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def insert_signal(self, **kwargs: Any) -> int | None:
        export_csv = bool(kwargs.pop("export_csv", False))
        row = {
            "time_utc": kwargs.get("time_utc", self._utc_now()),
            "pair": kwargs["pair"],
            "strategy": kwargs["strategy"],
            "session_gate": int(bool(kwargs.get("session_gate", False))),
            "spread_gate": int(bool(kwargs.get("spread_gate", False))),
            "news_gate": int(bool(kwargs.get("news_gate", False))),
            "open_pos_gate": int(bool(kwargs.get("open_pos_gate", False))),
            "daily_loss_gate": int(bool(kwargs.get("daily_loss_gate", False))),
            "enemy_gate": int(bool(kwargs.get("enemy_gate", False))),
            "signal": kwargs.get("signal", "HOLD"),
            "decision": kwargs.get("decision", "BLOCK"),
            "meta_json": self._to_json(kwargs.get("meta_json")),
        }

        inserted_id: int | None = None
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO signals (
                        time_utc,pair,strategy,session_gate,spread_gate,news_gate,open_pos_gate,
                        daily_loss_gate,enemy_gate,signal,decision,meta_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    tuple(row.values()),
                )
                inserted_id = int(cursor.lastrowid)
        except sqlite3.Error:
            export_csv = True

        if export_csv:
            self._append_csv(SIGNALS_CSV_PATH, row)

        return inserted_id

    def open_position(self, **kwargs: Any) -> int | None:
        export_csv = bool(kwargs.pop("export_csv", False))
        row = {
            "time_open_utc": kwargs.get("time_open_utc", self._utc_now()),
            "time_close_utc": None,
            "pair": kwargs["pair"],
            "strategy": kwargs["strategy"],
            "direction": kwargs["direction"],
            "units": int(kwargs["units"]),
            "entry_price": float(kwargs["entry_price"]),
            "exit_price": None,
            "sl_price": float(kwargs["sl_price"]),
            "tp_price": float(kwargs["tp_price"]),
            "result": None,
            "pnl_pips": None,
            "pnl_quote": None,
            "meta_json": self._to_json(kwargs.get("meta_json")),
        }

        inserted_id: int | None = None
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO trades (
                        time_open_utc,time_close_utc,pair,strategy,direction,units,entry_price,exit_price,
                        sl_price,tp_price,result,pnl_pips,pnl_quote,meta_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    tuple(row.values()),
                )
                inserted_id = int(cursor.lastrowid)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO positions (
                        pair,strategy,direction,units,entry_price,sl_price,tp_price,time_open_utc,is_open
                    ) VALUES (?,?,?,?,?,?,?,?,1)
                    """,
                    (
                        row["pair"],
                        row["strategy"],
                        row["direction"],
                        row["units"],
                        row["entry_price"],
                        row["sl_price"],
                        row["tp_price"],
                        row["time_open_utc"],
                    ),
                )
        except sqlite3.Error:
            export_csv = True

        if export_csv:
            self._append_csv(TRADES_CSV_PATH, row)
        return inserted_id

    def close_position(self, pair: str, **kwargs: Any) -> None:
        export_csv = bool(kwargs.pop("export_csv", False))
        close_time = kwargs.get("time_close_utc", self._utc_now())
        exit_price = float(kwargs["exit_price"])
        result = kwargs.get("result", "CLOSED")
        pnl_pips = float(kwargs.get("pnl_pips", 0.0))
        pnl_quote = float(kwargs.get("pnl_quote", 0.0))
        meta_json = self._to_json(kwargs.get("meta_json"))

        closed_row: dict[str, Any] | None = None
        try:
            with self._connect() as conn:
                trade = conn.execute(
                    "SELECT id,time_open_utc,pair,strategy,direction,units,entry_price,sl_price,tp_price FROM trades "
                    "WHERE pair=? AND time_close_utc IS NULL ORDER BY id DESC LIMIT 1",
                    (pair,),
                ).fetchone()
                if trade is None:
                    return

                conn.execute(
                    """
                    UPDATE trades
                    SET time_close_utc=?, exit_price=?, result=?, pnl_pips=?, pnl_quote=?, meta_json=?
                    WHERE id=?
                    """,
                    (close_time, exit_price, result, pnl_pips, pnl_quote, meta_json, int(trade[0])),
                )
                conn.execute("UPDATE positions SET is_open=0 WHERE pair=?", (pair,))
                conn.execute("DELETE FROM positions WHERE pair=?", (pair,))

                closed_row = {
                    "time_open_utc": trade[1],
                    "time_close_utc": close_time,
                    "pair": trade[2],
                    "strategy": trade[3],
                    "direction": trade[4],
                    "units": int(trade[5]),
                    "entry_price": float(trade[6]),
                    "exit_price": exit_price,
                    "sl_price": float(trade[7]),
                    "tp_price": float(trade[8]),
                    "result": result,
                    "pnl_pips": pnl_pips,
                    "pnl_quote": pnl_quote,
                    "meta_json": meta_json,
                }
        except sqlite3.Error:
            export_csv = True

        if export_csv and closed_row is not None:
            self._append_csv(TRADES_CSV_PATH, closed_row)

    def get_open_position(self, pair: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT pair,strategy,direction,units,entry_price,sl_price,tp_price,time_open_utc,is_open
                FROM positions WHERE pair=? AND is_open=1
                """,
                (pair,),
            ).fetchone()
        if row is None:
            return None
        keys = ["pair", "strategy", "direction", "units", "entry_price", "sl_price", "tp_price", "time_open_utc", "is_open"]
        return dict(zip(keys, row, strict=False))

    def list_open_positions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pair,strategy,direction,units,entry_price,sl_price,tp_price,time_open_utc,is_open
                FROM positions WHERE is_open=1 ORDER BY time_open_utc
                """
            ).fetchall()
        keys = ["pair", "strategy", "direction", "units", "entry_price", "sl_price", "tp_price", "time_open_utc", "is_open"]
        return [dict(zip(keys, row, strict=False)) for row in rows]

    def upsert_daily_stats(
        self,
        date_utc: str,
        start_balance: float,
        current_balance: float,
        realized_pnl: float,
        halted: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_stats (date_utc,start_balance,current_balance,realized_pnl,halted)
                VALUES (?,?,?,?,?)
                ON CONFLICT(date_utc) DO UPDATE SET
                    start_balance=excluded.start_balance,
                    current_balance=excluded.current_balance,
                    realized_pnl=excluded.realized_pnl,
                    halted=excluded.halted
                """,
                (date_utc, start_balance, current_balance, realized_pnl, int(bool(halted))),
            )

    def get_daily_stats(self, date_utc: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT date_utc,start_balance,current_balance,realized_pnl,halted FROM daily_stats WHERE date_utc=?",
                (date_utc,),
            ).fetchone()
        if row is None:
            return None
        keys = ["date_utc", "start_balance", "current_balance", "realized_pnl", "halted"]
        result = dict(zip(keys, row, strict=False))
        result["halted"] = bool(result["halted"])
        return result

    def set_halted(self, date_utc: str, halted: bool) -> None:
        existing = self.get_daily_stats(date_utc)
        if existing is None:
            self.upsert_daily_stats(date_utc, 0.0, 0.0, 0.0, halted)
            return
        self.upsert_daily_stats(
            date_utc=date_utc,
            start_balance=float(existing["start_balance"]),
            current_balance=float(existing["current_balance"]),
            realized_pnl=float(existing["realized_pnl"]),
            halted=halted,
        )
