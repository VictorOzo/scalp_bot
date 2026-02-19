"""Phase 8 paper trading runner with full gate logging."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.pairs import PAIR_STRATEGY_MAP
from config.settings import OANDA_ACCOUNT_ID, TIMEFRAME
from data.fetcher import get_candles, get_oanda_client
from execution.paper_broker import PaperBroker
from execution.kill_switch import close_all_positions
from execution.risk_manager import RISK_PER_TRADE, calculate_sl_tp
from execution.trade_store import TradeStore
from filters.market_state import is_strategy_allowed
from filters.news_filter import is_news_clear
from filters.session_filter import is_session_active
from filters.spread_filter import calculate_spread_pips, get_live_bid_ask, is_spread_acceptable
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap
from strategies import bb_breakout, ema_vwap, vwap_rsi

STRATEGIES = {
    "ema_vwap": ema_vwap,
    "bb_breakout": bb_breakout,
    "vwap_rsi": vwap_rsi,
}


def _logger() -> logging.Logger:
    logger = logging.getLogger("paper_run")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _prepare_df(strategy_name: str, df: pd.DataFrame) -> pd.DataFrame:
    out = calculate_atr(df.copy())
    out = calculate_adx(out)
    if strategy_name == "ema_vwap":
        out = calculate_ema(out, fast=9, slow=21)
        out = calculate_vwap(out)
    elif strategy_name == "bb_breakout":
        out = calculate_bollinger(out, period=20, std_mult=2.0)
    else:
        out = calculate_rsi(out, period=3)
        out = calculate_vwap(out)
    return out


def _position_units(balance: float, entry: float, sl: float, risk_pct: float = RISK_PER_TRADE) -> int:
    distance = abs(entry - sl)
    if distance <= 0:
        return 1
    risk_amount = balance * risk_pct
    units = int(max(1, risk_amount / distance))
    return units


def _evaluate_gates(pair: str, strategy_name: str, df: pd.DataFrame, bid: float, ask: float, broker: PaperBroker, halted: bool, now_utc: datetime | None = None) -> dict[str, bool]:
    session_gate = is_session_active(pair, now_utc=now_utc)
    spread_gate = is_spread_acceptable(pair, bid, ask)
    news_gate = is_news_clear(pair)
    open_pos_gate = not broker.has_open_position(pair)
    daily_loss_gate = not halted
    enemy_gate = is_strategy_allowed(strategy_name, df)
    return {
        "session_gate": session_gate,
        "spread_gate": spread_gate,
        "news_gate": news_gate,
        "open_pos_gate": open_pos_gate,
        "daily_loss_gate": daily_loss_gate,
        "enemy_gate": enemy_gate,
    }


MAX_DRAWDOWN = 0.03


def _run_pair(
    *,
    pair: str,
    strategy_name: str,
    df: pd.DataFrame,
    bid: float,
    ask: float,
    broker: PaperBroker,
    store: TradeStore,
    balance: float,
    export_csv: bool,
    halted: bool,
    now_utc: datetime | None = None,
) -> float:
    logger = _logger()
    gates = _evaluate_gates(pair, strategy_name, df, bid, ask, broker, halted, now_utc=now_utc)
    signal = STRATEGIES[strategy_name].generate_signal_from_df(df)
    decision = "EXECUTE" if all(gates.values()) and signal in {"BUY", "SELL"} else "BLOCK"

    logger.info("%s/%s gates=%s signal=%s decision=%s", pair, strategy_name, gates, signal, decision)
    store.insert_signal(
        pair=pair,
        strategy=strategy_name,
        signal=signal,
        decision=decision,
        meta_json={"spread_pips": calculate_spread_pips(pair, bid, ask)},
        export_csv=export_csv,
        **gates,
    )

    if decision == "EXECUTE":
        entry = ask if signal == "BUY" else bid
        atr = float(df.iloc[-1]["atr"])
        sl, tp = calculate_sl_tp(entry, signal, atr)
        units = _position_units(balance, entry, sl)
        broker.place_market_order(
            pair=pair,
            strategy=strategy_name,
            direction=signal,
            units=units,
            bid=bid,
            ask=ask,
            sl_price=sl,
            tp_price=tp,
            meta_json={"source": "paper_run"},
        )
    return balance


def run_offline(csv_path: Path, export_csv: bool = False) -> None:
    logger = _logger()
    store = TradeStore()
    store.init_db()
    broker = PaperBroker(store, export_csv=export_csv)

    frame = pd.read_csv(csv_path)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    pair = "EUR_USD"
    strategy_name = PAIR_STRATEGY_MAP[pair]

    today = datetime.now(timezone.utc).date().isoformat()
    stats = store.get_daily_stats(today) or {
        "start_balance": 10_000.0,
        "current_balance": 10_000.0,
        "realized_pnl": 0.0,
        "halted": False,
    }
    balance = float(stats["current_balance"])
    store.upsert_daily_stats(today, float(stats["start_balance"]), balance, float(stats["realized_pnl"]), bool(stats["halted"]))

    for idx in range(60, len(frame)):
        window = frame.iloc[: idx + 1].copy()
        calc_df = _prepare_df(strategy_name, window)

        close = float(window.iloc[-1]["close"])
        bid, ask = close - 0.00005, close + 0.00005
        halted = bool((store.get_daily_stats(today) or stats).get("halted", False))
        bar_time = window.iloc[-1]["time"].to_pydatetime()
        balance = _run_pair(
            pair=pair,
            strategy_name=strategy_name,
            df=calc_df,
            bid=bid,
            ask=ask,
            broker=broker,
            store=store,
            balance=balance,
            export_csv=export_csv,
            halted=halted,
            now_utc=bar_time,
        )
        closed = broker.update_positions_from_bar(
            pair,
            {
                "high": float(window.iloc[-1]["high"]),
                "low": float(window.iloc[-1]["low"]),
            },
            time_utc=str(window.iloc[-1]["time"].isoformat()),
        )
        if closed:
            realized = sum(float(t["pnl_quote"]) for t in closed)
            balance += realized
            stats = store.get_daily_stats(today) or stats
            new_realized = float(stats["realized_pnl"]) + realized
            start_balance = float(stats["start_balance"])
            drawdown = 0.0 if start_balance <= 0 else (start_balance - balance) / start_balance
            halted = drawdown >= MAX_DRAWDOWN
            store.upsert_daily_stats(
                date_utc=today,
                start_balance=start_balance,
                current_balance=balance,
                realized_pnl=new_realized,
                halted=halted,
            )
            if halted:
                close_all_positions(broker, reason="DAILY_LOSS_HALT")
                logger.warning("daily loss halt triggered drawdown=%.4f", drawdown)
                break

    logger.info("offline run complete")


def run_live(pairs: list[str], export_csv: bool = False) -> None:
    logger = _logger()
    store = TradeStore()
    store.init_db()
    broker = PaperBroker(store, export_csv=export_csv)
    client = get_oanda_client()
    if not OANDA_ACCOUNT_ID:
        raise ValueError("OANDA_ACCOUNT_ID required for LIVE mode")

    today = datetime.now(timezone.utc).date().isoformat()
    stats = store.get_daily_stats(today) or {
        "start_balance": 10_000.0,
        "current_balance": 10_000.0,
        "realized_pnl": 0.0,
        "halted": False,
    }

    store.upsert_daily_stats(today, float(stats["start_balance"]), float(stats["current_balance"]), float(stats["realized_pnl"]), bool(stats["halted"]))

    for pair in pairs:
        strategy_name = PAIR_STRATEGY_MAP[pair]
        candles = get_candles(pair, TIMEFRAME, count=150)
        calc_df = _prepare_df(strategy_name, candles)
        bid, ask = get_live_bid_ask(pair, client, OANDA_ACCOUNT_ID)
        _run_pair(
            pair=pair,
            strategy_name=strategy_name,
            df=calc_df,
            bid=bid,
            ask=ask,
            broker=broker,
            store=store,
            balance=float(stats["current_balance"]),
            export_csv=export_csv,
            halted=bool(stats["halted"]),
            now_utc=datetime.now(timezone.utc),
        )

        bar = candles.iloc[-1]
        closed = broker.update_positions_from_bar(pair, {"high": float(bar["high"]), "low": float(bar["low"])})
        if closed:
            realized = sum(float(t["pnl_quote"]) for t in closed)
            stats = store.get_daily_stats(today) or stats
            balance = float(stats["current_balance"]) + realized
            start_balance = float(stats["start_balance"])
            realized_total = float(stats["realized_pnl"]) + realized
            drawdown = 0.0 if start_balance <= 0 else (start_balance - balance) / start_balance
            halted = drawdown >= MAX_DRAWDOWN
            store.upsert_daily_stats(today, start_balance, balance, realized_total, halted)
            if halted:
                close_all_positions(broker, reason="DAILY_LOSS_HALT")
                logger.warning("daily loss halt triggered drawdown=%.4f", drawdown)
                break

    logger.info("live paper run cycle complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 paper trading runner")
    parser.add_argument("--mode", choices=["LIVE", "OFFLINE"], required=True)
    parser.add_argument("--pairs", default="EUR_USD,GBP_USD")
    parser.add_argument("--csv", default="tests/fixtures/sample_ohlcv.csv")
    parser.add_argument("--export-csv", action="store_true")
    args = parser.parse_args()

    if args.mode == "OFFLINE":
        run_offline(Path(args.csv), export_csv=args.export_csv)
    else:
        pairs = [pair.strip() for pair in args.pairs.split(",") if pair.strip()]
        run_live(pairs, export_csv=args.export_csv)


if __name__ == "__main__":
    main()
