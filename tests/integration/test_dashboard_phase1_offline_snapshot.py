from __future__ import annotations

from pathlib import Path

import pandas as pd

from indicators.adx import calculate_adx
from indicators.atr import calculate_atr
from indicators.bollinger import calculate_bollinger
from indicators.ema import calculate_ema
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.vwap import calculate_vwap
from storage.db import connect, init_db, write_gate_snapshot


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = calculate_atr(df)
    df = calculate_adx(df)
    df = calculate_ema(df)
    df = calculate_vwap(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger(df)
    return df


def test_offline_snapshot_write_from_fixture(tmp_path):
    fixture = Path("tests/fixtures/sample_ohlcv.csv")
    df = pd.read_csv(fixture)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")
    df = _compute_indicators(df)

    conn = connect(tmp_path / "dashboard_phase1.sqlite")
    try:
        init_db(conn)
        write_gate_snapshot(
            conn,
            ts_utc="2025-01-01T00:00:00+00:00",
            pair="EUR_USD",
            strategy="ema_vwap",
            session_ok=True,
            spread_ok=True,
            news_ok=True,
            open_pos_ok=True,
            daily_ok=True,
            enemy_ok=True,
            final_signal="HOLD",
            reason="offline_integration",
            details={"last_time": str(df.iloc[-1]["time"])},
        )

        row_count = conn.execute("SELECT COUNT(*) FROM gate_snapshots").fetchone()[0]
        pair = conn.execute("SELECT pair FROM gate_snapshots ORDER BY id DESC LIMIT 1").fetchone()[0]
    finally:
        conn.close()

    assert row_count == 1
    assert pair == "EUR_USD"
