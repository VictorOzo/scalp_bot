# config/settings.py
"""
Application settings for Arch 1 Forex scalping bot.
"""

from __future__ import annotations

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


OANDA_API_KEY: str | None = os.getenv("OANDA_API_KEY")
OANDA_ACCOUNT_ID: str | None = os.getenv("OANDA_ACCOUNT_ID")
OANDA_ENV: str = os.getenv("OANDA_ENV", "practice").strip().lower()

TIMEFRAME: Final[str] = "M5"
RISK_PER_TRADE: Final[float] = 0.01
DAILY_MAX_LOSS: Final[float] = 0.03
DEFAULT_CANDLE_COUNT: Final[int] = 200

DRY_RUN: bool = _env_bool("DRY_RUN", True)
LIVE_TRADING_ENABLED: bool = _env_bool("LIVE_TRADING_ENABLED", False)
COMMAND_POLL_INTERVAL_SEC: float = float(os.getenv("COMMAND_POLL_INTERVAL_SEC", "1.0"))
COMMAND_RUNNING_TIMEOUT_SEC: float = float(os.getenv("COMMAND_RUNNING_TIMEOUT_SEC", "300"))

API_JWT_SECRET: str = os.getenv("API_JWT_SECRET", "dev-insecure-secret")
API_JWT_ALG: str = os.getenv("API_JWT_ALG", "HS256")
API_JWT_EXPIRES_MIN: int = int(os.getenv("API_JWT_EXPIRES_MIN", str(60 * 24)))

API_COOKIE_NAME: str = os.getenv("API_COOKIE_NAME", "sb_auth")
API_COOKIE_SECURE: bool = _env_bool("API_COOKIE_SECURE", False)
API_COOKIE_SAMESITE: str = os.getenv("API_COOKIE_SAMESITE", "lax")

# IMPORTANT:
# For localhost development, DO NOT set API_COOKIE_DOMAIN.
# Leaving it unset makes the cookie "host-only" and reliable on localhost/127.0.0.1.
API_COOKIE_DOMAIN: str | None = os.getenv("API_COOKIE_DOMAIN")

ADMIN_BOOTSTRAP_USER: str | None = os.getenv("ADMIN_BOOTSTRAP_USER")
ADMIN_BOOTSTRAP_PASS: str | None = os.getenv("ADMIN_BOOTSTRAP_PASS")

RISK_PCT: float = float(os.getenv("RISK_PCT", "0.005"))
DEFAULT_UNITS: int = int(os.getenv("DEFAULT_UNITS", "1000"))
SL_ATR_MULT: float = float(os.getenv("SL_ATR_MULT", "1.5"))
TP_ATR_MULT: float = float(os.getenv("TP_ATR_MULT", "2.0"))


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