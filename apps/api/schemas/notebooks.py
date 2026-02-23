"""Pydantic-схемы для роутера notebooks."""
# --- Imports ---
from __future__ import annotations

from pydantic import BaseModel


# --- Models / Classes ---
class Notebook(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class CreateNotebookRequest(BaseModel):
    title: str


class UpdateNotebookRequest(BaseModel):
    title: str
