from execution.paper_broker import PaperBroker
from execution.trade_store import TradeStore


def test_paper_broker_buy_fill_and_tp(tmp_path):
    store = TradeStore(db_path=tmp_path / "paper.db")
    store.init_db()
    broker = PaperBroker(store)

    opened = broker.place_market_order(
        pair="EUR_USD",
        strategy="ema_vwap",
        direction="BUY",
        units=1000,
        bid=1.1000,
        ask=1.1002,
        sl_price=1.0990,
        tp_price=1.1010,
    )
    assert opened["entry_price"] == 1.1002
    closed = broker.update_positions_from_bar("EUR_USD", {"high": 1.1011, "low": 1.0995})
    assert closed
    assert closed[0]["result"] == "TP"
    assert closed[0]["pnl_pips"] > 0
