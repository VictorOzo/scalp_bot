from __future__ import annotations

import os
import sqlite3
from functools import lru_cache

from execution.alerts import AlertService, build_alert_service
from storage.db import get_app_settings


@lru_cache(maxsize=1)
def get_alert_service() -> AlertService:
    return build_alert_service(environment=os.getenv("APP_ENV", "prod"))


def get_alert_service_for_db(conn: sqlite3.Connection) -> AlertService:
    settings = get_app_settings(
        conn,
        keys=[
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "SMTP_FROM",
            "ALERT_EMAIL_TO",
            "SMTP_USE_STARTTLS",
            "SMTP_USE_SSL",
            "SMTP_TIMEOUT_SEC",
        ],
    )
    return build_alert_service(settings=settings, environment=os.getenv("APP_ENV", "prod"))
