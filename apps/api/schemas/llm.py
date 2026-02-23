"""Pydantic-схемы для роутера llm."""
# --- Imports ---
from __future__ import annotations

from pydantic import BaseModel


# --- Models / Classes ---
class IndexStatus(BaseModel):
    total: int
    indexed: int
    indexing: int
    failed: int
