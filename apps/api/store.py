"""Обратно-совместимый реэкспорт. Не добавлять сюда логику."""
# --- Imports ---
from __future__ import annotations

from .services.orchestrator import InMemoryStore, store  # noqa: F401
