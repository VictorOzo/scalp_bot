from execution.paper_broker import PaperBroker
from execution.trade_store import TradeStore


def test_has_open_position_uses_sqlite_state(tmp_path):
    store = TradeStore(db_path=tmp_path / "paper.db")
    store.init_db()
    broker = PaperBroker(store)

    assert broker.has_open_position("EUR_USD") is False
    store.open_position(
        pair="EUR_USD",
        strategy="ema_vwap",
        direction="SELL",
        units=1000,
        entry_price=1.1,
        sl_price=1.101,
        tp_price=1.099,
    )
    assert broker.has_open_position("EUR_USD") is True
