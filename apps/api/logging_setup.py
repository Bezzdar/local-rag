"""Настройка структуры и вывода логирования."""

# --- Imports ---
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LOGS_DIR

LOG_FILE = LOGS_DIR / "app.log"


# --- Основные блоки ---
class SafeExtraFormatter(logging.Formatter):
    """Formatter with stable keys even when `extra` is absent."""

    def format(self, record: logging.LogRecord) -> str:
        record.client_ip = getattr(record, "client_ip", "-")
        record.method = getattr(record, "method", "-")
        record.path = getattr(record, "path", "-")
        record.status_code = getattr(record, "status_code", "-")
        record.duration_ms = getattr(record, "duration_ms", "-")
        record.event = getattr(record, "event", "-")
        record.details = getattr(record, "details", "-")
        return super().format(record)


_CONFIGURED = False


def setup_logging() -> Path:
    global _CONFIGURED
    if _CONFIGURED:
        return LOG_FILE

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = SafeExtraFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s "
        "| event=%(event)s | method=%(method)s | path=%(path)s | status=%(status_code)s | "
        "duration_ms=%(duration_ms)s | ip=%(client_ip)s | details=%(details)s"
    )

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    _CONFIGURED = True
    root_logger.info(
        "Logging configured",
        extra={"event": "app.startup", "details": f"log_file={LOG_FILE}"},
    )
    return LOG_FILE
