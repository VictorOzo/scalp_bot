import sqlite3
from pathlib import Path

from tests.tools.paper_run import run_offline


def test_phase8_offline_paper_run_with_csv_and_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ohlcv.csv"

    run_offline(fixture, export_csv=True)
    run_offline(fixture, export_csv=True)

    db_path = tmp_path / "data" / "paper_trading.db"
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    try:
        signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        conn.execute("SELECT * FROM trades LIMIT 1").fetchall()
        positions = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    finally:
        conn.close()

    assert signals > 0
    assert positions <= 1
    assert (tmp_path / "data" / "signals_log.csv").exists()
    assert (tmp_path / "data" / "trades_log.csv").exists()
