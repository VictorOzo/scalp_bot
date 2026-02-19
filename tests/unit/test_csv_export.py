from execution.trade_store import SIGNALS_CSV_PATH, TRADES_CSV_PATH, TradeStore


def test_csv_export_appends_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = TradeStore(db_path=tmp_path / "paper.db")
    store.init_db()

    store.insert_signal(
        pair="EUR_USD",
        strategy="ema_vwap",
        session_gate=True,
        spread_gate=True,
        news_gate=True,
        open_pos_gate=True,
        daily_loss_gate=True,
        enemy_gate=True,
        signal="BUY",
        decision="EXECUTE",
        export_csv=True,
    )
    store.open_position(
        pair="EUR_USD",
        strategy="ema_vwap",
        direction="BUY",
        units=1000,
        entry_price=1.1,
        sl_price=1.099,
        tp_price=1.102,
        export_csv=True,
    )

    assert SIGNALS_CSV_PATH.exists()
    assert TRADES_CSV_PATH.exists()
    assert len(SIGNALS_CSV_PATH.read_text().strip().splitlines()) >= 2
    assert len(TRADES_CSV_PATH.read_text().strip().splitlines()) >= 2
