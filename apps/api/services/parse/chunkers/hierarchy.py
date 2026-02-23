"""Метод чанкинга Hierarchy: разбиение по структурным маркерам документа с breadcrumb."""
# --- Imports ---
from __future__ import annotations

import re
from typing import Optional

from ..constants import _HIERARCHY_PATTERNS
from ..models import ChunkType, ParsedChunk
from ..utils import _token_count
from .general import GeneralChunker


# --- Models / Classes ---
class HierarchyChunker(GeneralChunker):
    """Hierarchy: разбиение по структурным маркерам документа с breadcrumb."""

    def chunk(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        """Разбивает блоки по структурным паттернам с формированием breadcrumb-заголовков."""
        # Берем только заранее известные паттерны, иначе откатываемся к technical_manual.
        doc_type = self.config.doc_type if self.config.doc_type in _HIERARCHY_PATTERNS else "technical_manual"
        patterns = _HIERARCHY_PATTERNS[doc_type]

        chunks: list[ParsedChunk] = []
        hierarchy: dict[int, str] = {}  # level -> header text
        current_content_blocks: list[dict] = []

        # flush фиксирует накопленный раздел в один или несколько финальных чанков.
        def _flush(header_level: Optional[int] = None) -> None:
            nonlocal current_content_blocks
            if not current_content_blocks:
                return
            breadcrumb = self._build_breadcrumb(hierarchy)
            full_text = "\n".join(b["text"] for b in current_content_blocks)
            page_number = current_content_blocks[0].get("page_number")

            if _token_count(full_text) <= max(1, self.config.chunk_size):
                # Section fits in one chunk
                section_text = f"{breadcrumb}\n\n{full_text}".strip() if breadcrumb else full_text
                chunks.append(ParsedChunk(
                    text=section_text,
                    chunk_type=ChunkType.TEXT,
                    chunk_index=len(chunks),
                    page_number=page_number,
                    section_header=breadcrumb or None,
                    parent_header=None,
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                ))
            else:
                # Section too large: fallback to fixed chunking with breadcrumb prefix
                fake_block = {
                    "chunk_type": ChunkType.TEXT,
                    "page_number": page_number,
                    "section_header": breadcrumb or None,
                    "parent_header": None,
                }
                sub_chunks = self._chunk_text_block(
                    full_text, fake_block, doc_id, source_filename, len(chunks), ChunkType.TEXT
                )
                # Prepend breadcrumb to each sub-chunk
                for sub in sub_chunks:
                    if breadcrumb:
                        sub.text = f"{breadcrumb}\n\n{sub.text}".strip()
                    sub.chunk_index = len(chunks)
                    chunks.append(sub)

            current_content_blocks = []

        for block in blocks:
            if block["chunk_type"] == ChunkType.HEADER:
                header_level = self._detect_header_level(block["text"], patterns)
                if header_level is not None:
                    _flush(header_level)
                    # Clear sub-levels
                    hierarchy = {k: v for k, v in hierarchy.items() if k < header_level}
                    hierarchy[header_level] = re.sub(r"^#{1,6}\s*", "", block["text"])
                else:
                    # Unrecognized header: treat as content
                    current_content_blocks.append(block)
            else:
                current_content_blocks.append(block)

        _flush()

        # Apply overlap metadata
        for idx, chunk in enumerate(chunks):
            chunk.chunk_index = idx

        return chunks

    def _detect_header_level(self, text: str, patterns: list[tuple[int, re.Pattern]]) -> Optional[int]:
        # Проверяем заголовок на соответствие паттернам иерархии документа
        for level, pattern in patterns:
            if pattern.match(text):
                return level
        return None

    def _build_breadcrumb(self, hierarchy: dict[int, str]) -> str:
        # Собираем путь навигации из текущей иерархии заголовков
        parts = [hierarchy[level] for level in sorted(hierarchy.keys()) if hierarchy.get(level)]
        return " > ".join(parts) if parts else ""
