"""Метод чанкинга Symbol: разбиение по пользовательскому символу-разделителю."""
# --- Imports ---
from __future__ import annotations

from ..models import ChunkType, ParsedChunk
from .base import BaseChunker


# --- Models / Classes ---
class SymbolChunker(BaseChunker):
    """Symbol: разбиение по специальному символу-разделителю, расставленному пользователем."""

    def chunk(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        """Разбивает текст по символу-разделителю из конфигурации."""
        sep = self.config.symbol_separator or "---chunk---"

        # Join all block texts into full document text
        all_text = "\n".join(
            block["text"] for block in blocks
            if block["chunk_type"] != ChunkType.HEADER and block["text"].strip()
        )

        # Пользователь сам управляет семантическими границами через специальный разделитель.
        segments = [seg.strip() for seg in all_text.split(sep) if seg.strip()]

        if not segments:
            # Fallback: treat entire text as one chunk
            segments = [all_text.strip()] if all_text.strip() else []

        chunks: list[ParsedChunk] = []
        for idx, segment in enumerate(segments):
            chunks.append(ParsedChunk(
                text=segment,
                chunk_type=ChunkType.TEXT,
                chunk_index=idx,
                page_number=None,
                section_header=None,
                parent_header=None,
                prev_chunk_tail=None,
                next_chunk_head=None,
                doc_id=doc_id,
                source_filename=source_filename,
            ))

        return chunks
