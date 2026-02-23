"""Pydantic-схемы для роутера sources."""
# --- Imports ---
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Models / Classes ---
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
            "chunking_method": None,
            "context_window": None,
            "use_llm_summary": None,
            "doc_type": None,
            "parent_chunk_size": None,
            "child_chunk_size": None,
            "symbol_separator": None,
        }
    )


class ParsingSettings(BaseModel):
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50
    ocr_enabled: bool = True
    ocr_language: str = "rus+eng"
    auto_parse_on_upload: bool = False
    # Chunking method
    chunking_method: str = "general"
    # Context Enrichment params
    context_window: int = 128
    use_llm_summary: bool = False
    # Hierarchy params
    doc_type: str = "technical_manual"
    # PCR params
    parent_chunk_size: int = 1024
    child_chunk_size: int = 128
    # Symbol params
    symbol_separator: str = "---chunk---"


class AddPathRequest(BaseModel):
    path: str


class UpdateSourceRequest(BaseModel):
    is_enabled: bool | None = None
    individual_config: dict[str, int | bool | str | None] | None = None


class ReorderSourcesRequest(BaseModel):
    ordered_ids: list[str]
