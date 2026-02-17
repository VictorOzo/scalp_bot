"""Application settings for Arch 1 Forex scalping bot."""

from __future__ import annotations

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()

OANDA_API_KEY: str | None = os.getenv("OANDA_API_KEY")
OANDA_ACCOUNT_ID: str | None = os.getenv("OANDA_ACCOUNT_ID")
OANDA_ENV: str = os.getenv("OANDA_ENV", "practice").strip().lower()

TIMEFRAME: Final[str] = "M5"
RISK_PER_TRADE: Final[float] = 0.01
DAILY_MAX_LOSS: Final[float] = 0.03
DEFAULT_CANDLE_COUNT: Final[int] = 200


def validate_settings() -> None:
    """Validate runtime settings and required credentials."""
    missing: list[str] = []
    if not OANDA_API_KEY:
        missing.append("OANDA_API_KEY")
    if not OANDA_ACCOUNT_ID:
        missing.append("OANDA_ACCOUNT_ID")

    if missing:
        missing_vars: str = ", ".join(missing)
        raise ValueError(
            f"Missing required environment variable(s): {missing_vars}. "
            "Set them in your shell or in a .env file."
        )

    if OANDA_ENV not in {"practice", "live"}:
        raise ValueError("OANDA_ENV must be either 'practice' or 'live'.")
