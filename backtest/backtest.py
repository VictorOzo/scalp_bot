"""Offline backtesting engine components."""

from __future__ import annotations

import random
from typing import Literal

import pandas as pd

from execution.risk_manager import calculate_sl_tp
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap

TRADE_COSTS: dict[str, dict[str, float]] = {
    "EUR_USD": {"spread": 0.3, "max_slip": 0.5},
    "GBP_USD": {"spread": 0.8, "max_slip": 1.0},
    "USD_JPY": {"spread": 0.5, "max_slip": 0.7},
}


def pip_size(pair: str) -> float:
    """Return instrument pip size."""
    return 0.01 if pair.endswith("JPY") else 0.0001


def simulate_trade(
    future_df: pd.DataFrame,
    direction: Literal["BUY", "SELL"],
    raw_entry: float,
    sl: float,
    tp: float,
    pair: str,
    rng: random.Random | None = None,
) -> tuple[str, float, float]:
    """Simulate an SL/TP trade on future bars with spread/slippage costs."""
    if direction not in {"BUY", "SELL"}:
        raise ValueError("direction must be BUY or SELL")
    if future_df.empty:
        raise ValueError("future_df must not be empty")

    cfg = TRADE_COSTS.get(pair, {"spread": 0.5, "max_slip": 1.0})
    pip = pip_size(pair)
    rand = rng if rng is not None else random.Random()

    slip = rand.uniform(0, cfg["max_slip"]) * pip
    spread = (cfg["spread"] * pip) / 2.0

    if direction == "BUY":
        entry = raw_entry + spread + slip
        for _, row in future_df.iterrows():
            if float(row["low"]) <= sl:
                return "LOSS", (sl - entry) / pip, entry
            if float(row["high"]) >= tp:
                return "WIN", (tp - entry) / pip, entry
        last_close = float(future_df.iloc[-1]["close"])
        return "TIMEOUT", (last_close - entry) / pip, entry

    entry = raw_entry - spread - slip
    for _, row in future_df.iterrows():
        if float(row["high"]) >= sl:
            return "LOSS", (entry - sl) / pip, entry
        if float(row["low"]) <= tp:
            return "WIN", (entry - tp) / pip, entry

    last_close = float(future_df.iloc[-1]["close"])
    return "TIMEOUT", (entry - last_close) / pip, entry


def walk_forward_split(df: pd.DataFrame, train_pct: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataframe into train/validation copies."""
    if not 0 < train_pct < 1:
        raise ValueError("train_pct must be between 0 and 1")

    split_idx = int(len(df) * train_pct)
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def compute_metrics(trades_df: pd.DataFrame) -> dict[str, float]:
    """Compute backtest performance metrics in pips."""
    if trades_df.empty:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "gross_win_pips": 0.0,
            "gross_loss_pips": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "avg_pips_per_trade": 0.0,
        }

    pnl = trades_df["pnl_pips"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_win = float(wins.sum())
    gross_loss = float(losses.abs().sum())
    equity_curve = pnl.cumsum()
    peaks = equity_curve.cummax()
    drawdowns = peaks - equity_curve

    mean = float(pnl.mean())
    std = float(pnl.std(ddof=0))

    return {
        "total_trades": int(len(trades_df)),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "gross_win_pips": gross_win,
        "gross_loss_pips": gross_loss,
        "max_drawdown": float(drawdowns.max()) if not drawdowns.empty else 0.0,
        "sharpe": float(mean / std) if std > 0 else 0.0,
        "avg_pips_per_trade": mean,
    }


def _prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(out["time"]):
        out["time"] = pd.to_datetime(out["time"], utc=True)
    out = calculate_atr(out)
    out = calculate_adx(out)
    out = calculate_ema(out)
    out = calculate_vwap(out)
    out = calculate_rsi(out)
    out = calculate_bollinger(out)
    return out


def _run_segment(
    df: pd.DataFrame,
    pair: str,
    strategy_module,
    warmup: int,
    lookahead: int,
    mode: Literal["sl_tp", "time_exit"],
    hold_bars: int,
    rng: random.Random,
) -> pd.DataFrame:
    trades: list[dict[str, float | str | int]] = []
    i = warmup
    n = len(df)

    while i < n - 1:
        window = df.iloc[: i + 1]
        signal = strategy_module.generate_signal_from_df(window)
        if signal not in {"BUY", "SELL"}:
            i += 1
            continue

        if mode == "sl_tp":
            if i + lookahead >= n:
                break
            atr_val = float(df.iloc[i]["atr"])
            if atr_val <= 0:
                i += 1
                continue
            entry = float(df.iloc[i]["close"])
            sl, tp = calculate_sl_tp(entry, signal, atr_val)
            future = df.iloc[i + 1 : i + 1 + lookahead]
            result, pnl_pips, eff_entry = simulate_trade(future, signal, entry, sl, tp, pair, rng=rng)
            trades.append({"idx": i, "direction": signal, "result": result, "pnl_pips": pnl_pips, "entry": eff_entry})
            i += lookahead
            continue

        exit_idx = i + 1 + hold_bars
        if exit_idx >= n:
            break
        pip = pip_size(pair)
        entry = float(df.iloc[i + 1]["open"])
        exit_price = float(df.iloc[exit_idx]["close"])
        pnl_pips = (exit_price - entry) / pip if signal == "BUY" else (entry - exit_price) / pip
        result = "WIN" if pnl_pips > 0 else "LOSS" if pnl_pips < 0 else "TIMEOUT"
        trades.append({"idx": i, "direction": signal, "result": result, "pnl_pips": pnl_pips, "entry": entry})
        i = exit_idx

    return pd.DataFrame(trades)


def backtest_strategy(
    df: pd.DataFrame,
    pair: str,
    strategy_module,
    warmup: int = 60,
    lookahead: int = 50,
    train_pct: float = 0.7,
    seed: int = 123,
    mode: Literal["sl_tp", "time_exit"] = "sl_tp",
    hold_bars: int = 5,
    min_trades: int = 30,  # ✅ NEW
) -> dict[str, object]:
    """Run walk-forward backtest and return train/validation metrics."""
    if mode not in {"sl_tp", "time_exit"}:
        raise ValueError("mode must be 'sl_tp' or 'time_exit'")

    prepared = _prepare_indicators(df)
    train_df, validation_df = walk_forward_split(prepared, train_pct=train_pct)

    rng_train = random.Random(seed)
    rng_val = random.Random(seed + 1)

    train_trades = _run_segment(
        train_df, pair, strategy_module, warmup, lookahead, mode, hold_bars, rng_train
    )
    validation_trades = _run_segment(
        validation_df, pair, strategy_module, warmup, lookahead, mode, hold_bars, rng_val
    )

    train_metrics = compute_metrics(train_trades)
    validation_metrics = compute_metrics(validation_trades)
    gap = abs(float(train_metrics["win_rate"]) - float(validation_metrics["win_rate"]))

    train_n = int(train_metrics.get("total_trades", 0))
    val_n = int(validation_metrics.get("total_trades", 0))

    if train_n < min_trades or val_n < min_trades:
        overfit_warning = False
        overfit_reason = "insufficient_trades"
    else:
        overfit_warning = gap > 0.15
        overfit_reason = "gap_exceeds_threshold" if overfit_warning else ""

    return {
        "train": train_metrics,
        "validation": validation_metrics,
        "gap": gap,
        "overfit_warning": overfit_warning,
        "overfit_reason": overfit_reason,
    }