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
