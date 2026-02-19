from execution.trade_store import TradeStore


def test_trade_store_sqlite_roundtrip(tmp_path):
    store = TradeStore(db_path=tmp_path / "paper.db")
    store.init_db()

    signal_id = store.insert_signal(
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
    )
    assert signal_id is not None

    trade_id = store.open_position(
        pair="EUR_USD",
        strategy="ema_vwap",
        direction="BUY",
        units=1000,
        entry_price=1.1,
        sl_price=1.099,
        tp_price=1.102,
    )
    assert trade_id is not None
    pos = store.get_open_position("EUR_USD")
    assert pos is not None

    store.close_position("EUR_USD", exit_price=1.102, result="TP", pnl_pips=20, pnl_quote=20)
    assert store.get_open_position("EUR_USD") is None

    store.upsert_daily_stats("2024-01-01", 10000, 10020, 20, False)
    stats = store.get_daily_stats("2024-01-01")
    assert stats is not None
    assert stats["current_balance"] == 10020
