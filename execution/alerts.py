"""Operational alerts with email-first delivery and payload sanitization."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from enum import Enum
from typing import Any, Protocol

SECRET_PATTERNS = ("token", "password", "api_key", "authorization", "smtp_pass", "secret")
MAX_ALERT_BODY_LEN = 2000
DEFAULT_DEDUPE_SECONDS = 60


class AlertEvent(str, Enum):
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    DAILY_HALT = "DAILY_HALT"
    BOT_RESTART = "BOT_RESTART"
    KILL_SWITCH = "KILL_SWITCH"


ALERT_WHITELIST: dict[AlertEvent, tuple[str, ...]] = {
    AlertEvent.TRADE_OPEN: ("pair", "strategy", "direction", "units", "entry_price", "sl_price", "tp_price", "time_utc"),
    AlertEvent.TRADE_CLOSE: ("pair", "strategy", "direction", "result", "exit_price", "pnl_pips", "pnl_quote", "time_utc"),
    AlertEvent.DAILY_HALT: ("date_utc", "drawdown", "threshold", "mode"),
    AlertEvent.BOT_RESTART: ("service", "handled_by", "startup_time_utc", "version"),
    AlertEvent.KILL_SWITCH: ("enabled", "source", "reason", "pairs_closed", "time_utc"),
}


class AlertProvider(Protocol):
    def send(self, *, event: AlertEvent, subject: str, body: str) -> None: ...


@dataclass
class EmailConfig:
    host: str
    port: int
    user: str | None
    password: str | None
    from_email: str
    to_email: str
    use_starttls: bool
    use_ssl: bool
    timeout_sec: float


class EmailProvider:
    def __init__(self, config: EmailConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("scalp_bot.alerts")

    def send(self, *, event: AlertEvent, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.config.from_email
        msg["To"] = self.config.to_email
        msg["Subject"] = subject
        msg.set_content(body)

        for attempt in range(2):
            try:
                if self.config.use_ssl:
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(self.config.host, self.config.port, timeout=self.config.timeout_sec, context=context) as server:
                        if self.config.user and self.config.password:
                            server.login(self.config.user, self.config.password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(self.config.host, self.config.port, timeout=self.config.timeout_sec) as server:
                        if self.config.use_starttls:
                            server.starttls(context=ssl.create_default_context())
                        if self.config.user and self.config.password:
                            server.login(self.config.user, self.config.password)
                        server.send_message(msg)
                return
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("alert send failed event=%s attempt=%s err=%s", event.value, attempt + 1, exc)
                if attempt == 0:
                    time.sleep(0.15)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_email_config(settings: dict[str, Any] | None = None) -> EmailConfig | None:
    s = settings or {}
    host = str(s.get("SMTP_HOST") or os.getenv("SMTP_HOST", "")).strip()
    if not host:
        return None
    port = int(s.get("SMTP_PORT") or os.getenv("SMTP_PORT", "587"))
    user = (s.get("SMTP_USER") or os.getenv("SMTP_USER"))
    password = (s.get("SMTP_PASS") or os.getenv("SMTP_PASS"))
    from_email = str(s.get("SMTP_FROM") or os.getenv("SMTP_FROM", user or "scalp-bot@localhost")).strip()
    to_email = str(s.get("ALERT_EMAIL_TO") or os.getenv("ALERT_EMAIL_TO", "ozokweluvic@gmail.com")).strip()
    return EmailConfig(
        host=host,
        port=port,
        user=str(user) if user else None,
        password=str(password) if password else None,
        from_email=from_email,
        to_email=to_email,
        use_starttls=_env_bool("SMTP_USE_STARTTLS", True) if "SMTP_USE_STARTTLS" not in s else bool(s["SMTP_USE_STARTTLS"]),
        use_ssl=_env_bool("SMTP_USE_SSL", False) if "SMTP_USE_SSL" not in s else bool(s["SMTP_USE_SSL"]),
        timeout_sec=float(s.get("SMTP_TIMEOUT_SEC") or os.getenv("SMTP_TIMEOUT_SEC", "10")),
    )


def _sanitize(event: AlertEvent, payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload or {}
    allowed = ALERT_WHITELIST[event]
    clean: dict[str, Any] = {}
    for key in allowed:
        value = source.get(key)
        if value is None:
            continue
        clean[key] = value
    return clean


def _contains_secret(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in SECRET_PATTERNS)


class AlertService:
    def __init__(
        self,
        providers: list[AlertProvider],
        *,
        environment: str = "prod",
        dedupe_seconds: int = DEFAULT_DEDUPE_SECONDS,
        logger: logging.Logger | None = None,
    ) -> None:
        self.providers = providers
        self.environment = environment
        self.dedupe_seconds = dedupe_seconds
        self.logger = logger or logging.getLogger("scalp_bot.alerts")
        self._recent: dict[str, float] = {}

    def send(self, event: AlertEvent, payload: dict[str, Any] | None = None) -> bool:
        clean = _sanitize(event, payload)
        fingerprint = f"{event.value}:{json.dumps(clean, sort_keys=True, default=str)}"
        now = time.monotonic()
        seen = self._recent.get(fingerprint)
        if seen is not None and (now - seen) < self.dedupe_seconds:
            return False
        self._recent[fingerprint] = now

        subject_core = str(clean.get("pair") or clean.get("service") or "bot")
        subject = f"[{self.environment}][{event.value}] {subject_core}"
        body = json.dumps(clean, indent=2, sort_keys=True, default=str)
        if len(body) > MAX_ALERT_BODY_LEN:
            body = f"{body[:MAX_ALERT_BODY_LEN]}\n...<truncated>"
        if _contains_secret(body) or _contains_secret(subject):
            self.logger.error("alert dropped due to secret-like content event=%s", event.value)
            return False

        for provider in self.providers:
            try:
                provider.send(event=event, subject=subject, body=body)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("provider failed event=%s err=%s", event.value, exc)
        return True


def build_alert_service(*, settings: dict[str, Any] | None = None, environment: str = "prod") -> AlertService:
    providers: list[AlertProvider] = []
    email_config = load_email_config(settings=settings)
    if email_config is not None:
        providers.append(EmailProvider(email_config))
    return AlertService(providers, environment=environment)
