"""Pydantic-схемы для роутеров citations и global_notes."""
# --- Imports ---
from __future__ import annotations

from pydantic import BaseModel, Field

from .chat import CitationLocation


# --- Models / Classes ---
class SavedCitation(BaseModel):
    """Persistent citation saved by user from chat response."""
    id: str
    notebook_id: str
    source_id: str
    filename: str
    doc_order: int
    chunk_text: str
    location: CitationLocation
    created_at: str
    # Source traceability metadata
    source_notebook_id: str  # Which notebook owns this source
    source_type: str = "notebook"  # "notebook" or "database"


class SaveCitationRequest(BaseModel):
    source_id: str
    filename: str
    doc_order: int
    chunk_text: str
    page: int | None = None
    sheet: str | None = None
    source_notebook_id: str
    source_type: str = "notebook"


class GlobalNote(BaseModel):
    """Global persistent note saved from chat response (cross-notebook)."""
    id: str
    content: str
    source_notebook_id: str
    source_notebook_title: str
    created_at: str
    # List of source references embedded in this note
    source_refs: list[dict[str, str | int]] = Field(default_factory=list)


class CreateGlobalNoteRequest(BaseModel):
    content: str
    source_notebook_id: str
    source_notebook_title: str
    source_refs: list[dict[str, str | int]] = Field(default_factory=list)
