"""Модели данных модуля парсинга: типы чанков, конфигурация, метаданные."""
# --- Imports ---
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# --- Models / Classes ---
class UnsupportedFormatError(Exception):
    pass


class ParseError(Exception):
    pass


class ChunkType(Enum):
    TEXT = "text"
    TABLE = "table"
    FORMULA = "formula"
    HEADER = "header"
    CAPTION = "caption"


@dataclass
class ParserConfig:
    """Глобальные настройки парсинга и чанкинга.

    Значения выступают дефолтами и могут переопределяться для конкретного
    источника через ``individual_config``.
    """
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50
    ocr_enabled: bool = True
    ocr_language: str = "rus+eng"
    # Chunking method selection
    chunking_method: str = "general"
    # Context Enrichment params
    context_window: int = 128
    use_llm_summary: bool = False
    # Hierarchy params
    doc_type: str = "technical_manual"
    # PCR (Parent-Child Retrieval) params
    parent_chunk_size: int = 1024
    child_chunk_size: int = 128
    # Symbol separator params
    symbol_separator: str = "---chunk---"


@dataclass
class ParsedChunk:
    """Нормализованная модель чанка для БД, поиска и ответа LLM."""
    text: str
    chunk_type: ChunkType
    chunk_index: int
    page_number: Optional[int]
    section_header: Optional[str]
    parent_header: Optional[str]
    prev_chunk_tail: Optional[str]
    next_chunk_head: Optional[str]
    doc_id: str
    source_filename: str
    # Optional fields for advanced chunking methods
    embedding_text: Optional[str] = None   # Text used for embedding (differs from display text in CE/PCR)
    parent_chunk_id: Optional[str] = None  # For PCR: child chunks reference their parent


@dataclass
class DocumentMetadata:
    """Метаданные документа и конфигурации, с которой он был распарсен."""
    doc_id: str
    notebook_id: str
    filename: str
    filepath: str
    file_hash: str
    file_size_bytes: int
    title: Optional[str]
    authors: Optional[list[str]]
    year: Optional[int]
    source: Optional[str]
    total_pages: Optional[int]
    total_chunks: int
    language: str
    parser_version: str
    parsed_at: str
    tags: list[str] = field(default_factory=list)
    user_notes: Optional[str] = None
    is_enabled: bool = True
    individual_config: dict[str, int | bool | str | None] = field(
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
    chunking_method: str = "general"
