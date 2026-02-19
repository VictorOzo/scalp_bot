"""Paper broker with instant bid/ask fills and candle-based SL/TP reconciliation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from execution.trade_store import TradeStore


class PaperBroker:
    def __init__(self, store: TradeStore, export_csv: bool = False) -> None:
        self.store = store
        self.export_csv = export_csv

    @staticmethod
    def _pip_size(pair: str) -> float:
        return 0.01 if pair.endswith("JPY") else 0.0001

    def has_open_position(self, pair: str) -> bool:
        return self.store.get_open_position(pair) is not None

    def place_market_order(
        self,
        pair: str,
        strategy: str,
        direction: str,
        units: int,
        bid: float,
        ask: float,
        sl_price: float,
        tp_price: float,
        meta_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if direction not in {"BUY", "SELL"}:
            raise ValueError("direction must be BUY or SELL")

        entry_price = ask if direction == "BUY" else bid
        opened = {
            "pair": pair,
            "strategy": strategy,
            "direction": direction,
            "units": int(units),
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp_price": float(tp_price),
            "time_open_utc": datetime.now(timezone.utc).isoformat(),
            "meta_json": meta_json or {},
        }
        self.store.open_position(**opened, export_csv=self.export_csv)
        return opened

    def _close_position(
        self,
        position: dict[str, Any],
        exit_price: float,
        result: str,
        close_time: str,
        meta_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pair = str(position["pair"])
        pip = self._pip_size(pair)
        entry = float(position["entry_price"])
        units = int(position["units"])
        direction = str(position["direction"])
        pnl_pips = (exit_price - entry) / pip if direction == "BUY" else (entry - exit_price) / pip
        pnl_quote = pnl_pips * pip * units

        self.store.close_position(
            pair,
            exit_price=exit_price,
            result=result,
            pnl_pips=pnl_pips,
            pnl_quote=pnl_quote,
            time_close_utc=close_time,
            meta_json=meta_json,
            export_csv=self.export_csv,
        )
        return {
            "pair": pair,
            "result": result,
            "exit_price": exit_price,
            "pnl_pips": pnl_pips,
            "pnl_quote": pnl_quote,
        }

    def update_positions_from_bar(self, pair: str, bar: dict[str, float], time_utc: str | None = None) -> list[dict[str, Any]]:
        position = self.store.get_open_position(pair)
        if position is None:
            return []

        high = float(bar["high"])
        low = float(bar["low"])
        direction = str(position["direction"])
        sl = float(position["sl_price"])
        tp = float(position["tp_price"])
        close_time = time_utc or datetime.now(timezone.utc).isoformat()

        if direction == "BUY":
            if low <= sl:
                return [self._close_position(position, sl, "SL", close_time, {"reason": "sl_hit"})]
            if high >= tp:
                return [self._close_position(position, tp, "TP", close_time, {"reason": "tp_hit"})]
        else:
            if high >= sl:
                return [self._close_position(position, sl, "SL", close_time, {"reason": "sl_hit"})]
            if low <= tp:
                return [self._close_position(position, tp, "TP", close_time, {"reason": "tp_hit"})]

        return []

    def close_all_positions(self, exit_prices: dict[str, float] | None = None, reason: str = "KILL_SWITCH") -> list[dict[str, Any]]:
        closed: list[dict[str, Any]] = []
        close_time = datetime.now(timezone.utc).isoformat()
        for position in self.store.list_open_positions():
            pair = str(position["pair"])
            fallback = float(position["entry_price"])
            exit_price = float((exit_prices or {}).get(pair, fallback))
            closed.append(self._close_position(position, exit_price, reason, close_time, {"reason": reason.lower()}))
        return closed
