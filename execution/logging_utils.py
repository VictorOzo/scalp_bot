from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_rotating_logger(name: str, *, file_path: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    retention = int(os.getenv("LOG_RETENTION_DAYS", "7"))
    rotating = TimedRotatingFileHandler(file_path, when="midnight", backupCount=retention, encoding="utf-8")
    rotating.setLevel(logging.INFO)
    rotating.setFormatter(logging.Formatter("%(asctime)s,%(levelname)s,%(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"))

    logger.addHandler(console)
    logger.addHandler(rotating)
    return logger
