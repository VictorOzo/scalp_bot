"""Main runtime loop for Phase 5 paper-first execution flow."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from config.pairs import PAIR_STRATEGY_MAP
from config.settings import (
    DRY_RUN,
    OANDA_ACCOUNT_ID,
    TIMEFRAME,
    validate_settings,
)
from data.fetcher import get_candles, get_oanda_client
from execution.order_manager import can_open_new_position, place_market_order
from execution.risk_manager import (
    MAX_OPEN_POSITIONS_TOTAL,
    calculate_position_size,
    calculate_sl_tp,
    get_instrument_specs,
    is_within_daily_limit,
)
from filters.spread_filter import get_live_bid_ask
from indicators.atr import calculate_atr
from strategies import bb_breakout, ema_vwap, vwap_rsi

STRATEGY_FN = {
    "ema_vwap": ema_vwap.get_signal,
    "bb_breakout": bb_breakout.get_signal,
    "vwap_rsi": vwap_rsi.get_signal,
}


def setup_logging() -> logging.Logger:
    """Configure application logging for console and CSV log file."""
    logger = logging.getLogger("scalp_bot")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    file_handler = logging.FileHandler("logs/trade_log.csv")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s,%(levelname)s,%(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def seconds_until_next_candle(timeframe_minutes: int = 5) -> float:
    """Return seconds remaining until the next candle boundary in UTC."""
    now = datetime.now(timezone.utc)
    period_seconds = timeframe_minutes * 60
    elapsed = (now.minute * 60 + now.second) % period_seconds
    remaining = period_seconds - elapsed
    if remaining <= 0:
        return float(period_seconds)
    return float(remaining)



def execute_cycle(client, account_id: str, logger: logging.Logger) -> None:
    """Execute one scan-trade cycle across configured pairs."""
    for pair, strategy_name in PAIR_STRATEGY_MAP.items():
        signal_fn = STRATEGY_FN[strategy_name]
        direction = signal_fn(client, account_id)
        if direction == "HOLD":
            continue

        if not can_open_new_position(
            pair, client, account_id, max_total=MAX_OPEN_POSITIONS_TOTAL
        ):
            logger.info("SKIP %s %s: position limits reached", pair, strategy_name)
            continue

        if not is_within_daily_limit(client, account_id):
            logger.info("SKIP %s %s: daily loss limit reached", pair, strategy_name)
            continue

        bid, ask = get_live_bid_ask(pair, client, account_id)
        entry_price = ask if direction == "BUY" else bid

        df = get_candles(pair, TIMEFRAME, count=150)
        df = calculate_atr(df)
        atr = float(df.iloc[-1]["atr"])

        sl_price, tp_price = calculate_sl_tp(entry_price, direction, atr)

        try:
            from oandapyV20.endpoints.accounts import AccountSummary

            endpoint = AccountSummary(accountID=account_id)
            response = client.request(endpoint)
            balance = float(response["account"]["balance"])
        except Exception:
            specs = get_instrument_specs(pair, client, account_id)
            units = int(specs.get("min_units", 1))
        else:
            units = calculate_position_size(
                pair=pair,
                entry=entry_price,
                sl_price=sl_price,
                balance=balance,
                client=client,
                account_id=account_id,
            )

        if DRY_RUN:
            print(
                f"DRY_RUN {pair} {direction} units={units} entry={entry_price:.5f} "
                f"sl={sl_price} tp={tp_price}"
            )
            continue

        response = place_market_order(
            pair=pair,
            direction=direction,
            units=units,
            sl_price=sl_price,
            tp_price=tp_price,
            client=client,
            account_id=account_id,
        )
        logger.info("ORDER %s %s placed: %s", pair, direction, response)


def run() -> None:
    """Run a candle-synced execution loop."""
    logger = setup_logging()
    validate_settings()
    client = get_oanda_client()

    logger.info("Phase 5 engine started. DRY_RUN=%s", DRY_RUN)

    while True:
        wait_seconds = seconds_until_next_candle(timeframe_minutes=5)
        logger.info("Waiting %.1f seconds for next candle close.", wait_seconds)
        time.sleep(wait_seconds)
        execute_cycle(client, OANDA_ACCOUNT_ID, logger)


if __name__ == "__main__":
    run()
