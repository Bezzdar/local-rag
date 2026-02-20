from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


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


class CreateNoteRequest(BaseModel):
    title: str
    content: str


class UpdateNoteRequest(BaseModel):
    title: str
    content: str


class IndexStatus(BaseModel):
    total: int
    indexed: int
    indexing: int
    failed: int
