"""Pydantic-схемы контрактов API."""

# --- Imports ---
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# --- Основные блоки ---
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Notebook(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class Source(BaseModel):
    id: str
    notebook_id: str
    filename: str
    file_path: str
    file_type: Literal["pdf", "docx", "xlsx", "other"]
    size_bytes: int
    status: Literal["new", "indexing", "indexed", "failed"]
    added_at: str
    is_enabled: bool = True
    has_docs: bool = True
    has_parsing: bool = False
    has_base: bool = False
    embeddings_status: Literal["available", "unavailable"] = "available"
    index_warning: str | None = None
    sort_order: int = 0
    individual_config: dict[str, int | bool | str | None] = Field(
        default_factory=lambda: {
            "chunk_size": None,
            "chunk_overlap": None,
            "ocr_enabled": None,
            "ocr_language": None,
        }
    )


class ParsingSettings(BaseModel):
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50
    ocr_enabled: bool = True
    ocr_language: str = "rus+eng"
    auto_parse_on_upload: bool = False


class ChatMessage(BaseModel):
    id: str
    notebook_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class CitationLocation(BaseModel):
    page: int | None = None
    sheet: str | None = None
    paragraph: int | None = None


class Citation(BaseModel):
    id: str
    notebook_id: str
    source_id: str
    filename: str
    location: CitationLocation
    snippet: str
    score: float = Field(ge=0.0, le=1.0)
    doc_order: int = 0  # Sequential document number in notebook


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


class GlobalNote(BaseModel):
    """Global persistent note saved from chat response (cross-notebook)."""
    id: str
    content: str
    source_notebook_id: str
    source_notebook_title: str
    created_at: str
    # List of source references embedded in this note
    source_refs: list[dict[str, str | int]] = Field(default_factory=list)


class Note(BaseModel):
    id: str
    notebook_id: str
    title: str
    content: str
    created_at: str


class ChatRequest(BaseModel):
    notebook_id: str
    message: str
    selected_source_ids: list[str] = Field(default_factory=list)
    mode: Literal["model", "agent", "rag"]
    provider: str = "none"
    model: str = ""
    base_url: str = ""


class ChatResponse(BaseModel):
    message: ChatMessage
    citations: list[Citation]


class CreateNotebookRequest(BaseModel):
    title: str


class UpdateNotebookRequest(BaseModel):
    title: str


class AddPathRequest(BaseModel):
    path: str


class UpdateSourceRequest(BaseModel):
    is_enabled: bool | None = None
    individual_config: dict[str, int | bool | str | None] | None = None


class ReorderSourcesRequest(BaseModel):
    ordered_ids: list[str]


class CreateNoteRequest(BaseModel):
    title: str
    content: str


class UpdateNoteRequest(BaseModel):
    title: str
    content: str


class SaveCitationRequest(BaseModel):
    source_id: str
    filename: str
    doc_order: int
    chunk_text: str
    page: int | None = None
    sheet: str | None = None
    source_notebook_id: str
    source_type: str = "notebook"


class CreateGlobalNoteRequest(BaseModel):
    content: str
    source_notebook_id: str
    source_notebook_title: str
    source_refs: list[dict[str, str | int]] = Field(default_factory=list)


class IndexStatus(BaseModel):
    total: int
    indexed: int
    indexing: int
    failed: int
