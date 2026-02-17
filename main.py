"""Main runtime loop for Arch 1 Phase 1 infrastructure."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from config.settings import OANDA_ACCOUNT_ID, TIMEFRAME, validate_settings
from data.fetcher import get_oanda_client, stream_price_tick


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
    now = datetime.now(UTC)
    period_seconds = timeframe_minutes * 60
    elapsed = (now.minute * 60 + now.second) % period_seconds
    remaining = period_seconds - elapsed
    if remaining <= 0:
        return float(period_seconds)
    return float(remaining)


def run() -> None:
    """Run a candle-synchronized loop with basic API connectivity checks."""
    logger = setup_logging()
    validate_settings()

    try:
        client = get_oanda_client()
        logger.info("Connected to OANDA %s environment.", client.environment)

        tick = stream_price_tick("EUR_USD")
        if tick:
            logger.info("Streaming test successful for EUR_USD at %s", tick.get("time"))
        else:
            logger.warning("Streaming test did not return a price tick.")
    except Exception as exc:
        logger.exception("Failed to initialize data connectivity: %s", exc)
        raise

    logger.info("Starting %s candle-synchronized loop for account %s", TIMEFRAME, OANDA_ACCOUNT_ID)

    while True:
        wait_seconds = seconds_until_next_candle(timeframe_minutes=5)
        logger.info("Waiting %.1f seconds for next candle close.", wait_seconds)
        time.sleep(wait_seconds)

        cycle_time = datetime.now(UTC).replace(second=0, microsecond=0)
        logger.info("Candle cycle triggered at %s", cycle_time.isoformat())


if __name__ == "__main__":
    run()
