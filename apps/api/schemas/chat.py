"""Pydantic-схемы для роутера chat."""
# --- Imports ---
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Models / Classes ---
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
