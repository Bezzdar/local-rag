"""Общие утилиты и базовые типы, переиспользуемые в нескольких схемах."""
# --- Imports ---
from __future__ import annotations

from datetime import datetime, timezone


# --- Functions ---
def now_iso() -> str:
    """Возвращает текущее время в формате ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()
