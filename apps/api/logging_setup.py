"""Настройка структуры и вывода логирования.

Логи разделяются на два файла в рамках одной сессии (= один запуск бэкенда):
  - app_<SESSION_ID>.log  — серверные события (HTTP, индексация, ошибки)
  - ui_<SESSION_ID>.log   — клиентские UI-события (нажатия кнопок, действия пользователя)

При непрерывной работе файлы ротируются каждые 4 часа (до 12 ротаций на сессию).
Все файлы хранятся в data/logs/sessions/.
"""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .config import LOGS_DIR

# Идентификатор сессии — дата и время запуска бэкенда (один раз при импорте)
SESSION_ID: str = datetime.now().strftime("%Y-%m-%d_%H-%M")

SESSIONS_DIR: Path = LOGS_DIR / "sessions"
APP_LOG_FILE: Path = SESSIONS_DIR / f"app_{SESSION_ID}.log"
UI_LOG_FILE: Path = SESSIONS_DIR / f"ui_{SESSION_ID}.log"


# --- Форматтеры ---

class SafeExtraFormatter(logging.Formatter):
    """Formatter со стабильными extra-полями (подставляет '-' если поле отсутствует)."""

    _EXTRA_FIELDS = ("client_ip", "method", "path", "status_code", "duration_ms", "event", "details")

    def format(self, record: logging.LogRecord) -> str:
        for field in self._EXTRA_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "-")
        return super().format(record)


_APP_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    " | event=%(event)s | method=%(method)s | path=%(path)s"
    " | status=%(status_code)s | duration_ms=%(duration_ms)s"
    " | ip=%(client_ip)s | details=%(details)s"
)

_UI_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(message)s"
    " | event=%(event)s | details=%(details)s"
)


# --- Фильтры ---

class _ExcludeClientEventsFilter(logging.Filter):
    """Пропускает все записи, кроме client.*-событий (они идут в ui-лог)."""

    def filter(self, record: logging.LogRecord) -> bool:
        event = getattr(record, "event", "-")
        return not str(event).startswith("client.")


class _OnlyClientEventsFilter(logging.Filter):
    """Пропускает только client.*-события (для ui-лога)."""

    def filter(self, record: logging.LogRecord) -> bool:
        event = getattr(record, "event", "-")
        return str(event).startswith("client.")


# --- Настройка ---

_CONFIGURED = False


def setup_logging() -> tuple[Path, Path]:
    """Настраивает логирование и возвращает пути (app_log, ui_log)."""
    global _CONFIGURED
    if _CONFIGURED:
        return APP_LOG_FILE, UI_LOG_FILE

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Убрать все существующие хендлеры
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    app_formatter = SafeExtraFormatter(_APP_FORMAT)
    ui_formatter = SafeExtraFormatter(_UI_FORMAT)

    # --- Файловый хендлер серверных логов (app_*.log) ---
    # Ротация каждые 4 часа, хранить до 12 файлов (48 ч непрерывной работы)
    app_file_handler = TimedRotatingFileHandler(
        APP_LOG_FILE, when="H", interval=4, backupCount=12, encoding="utf-8"
    )
    app_file_handler.setFormatter(app_formatter)
    app_file_handler.addFilter(_ExcludeClientEventsFilter())

    # --- Файловый хендлер UI-событий (ui_*.log) ---
    ui_file_handler = TimedRotatingFileHandler(
        UI_LOG_FILE, when="H", interval=4, backupCount=12, encoding="utf-8"
    )
    ui_file_handler.setFormatter(ui_formatter)
    ui_file_handler.addFilter(_OnlyClientEventsFilter())

    # --- Консольный хендлер (все логи) ---
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(app_formatter)

    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(ui_file_handler)
    root_logger.addHandler(stream_handler)

    _CONFIGURED = True
    root_logger.info(
        "Logging configured",
        extra={
            "event": "app.startup",
            "details": f"session={SESSION_ID} | app_log={APP_LOG_FILE} | ui_log={UI_LOG_FILE}",
        },
    )
    return APP_LOG_FILE, UI_LOG_FILE
