"""Реэкспорт публичного API модуля notebook_db."""
# --- Imports ---
from __future__ import annotations

from .db import NotebookDB, db_for_notebook  # noqa: F401

__all__ = ["NotebookDB", "db_for_notebook"]
