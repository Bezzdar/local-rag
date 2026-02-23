"""Метод чанкинга Context Enrichment: каждый чанк обогащается контекстом соседних фрагментов."""
# --- Imports ---
from __future__ import annotations

from ..models import ParsedChunk
from .general import GeneralChunker


# --- Models / Classes ---
class ContextEnrichmentChunker(GeneralChunker):
    """Context Enrichment: каждый чанк получает контекстную обёртку из соседних фрагментов."""

    def chunk(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        """Разбивает блоки на чанки с добавлением контекста из соседних фрагментов."""
        # Step 1: базовое разбиение (как General).
        chunks = super().chunk(blocks, doc_id=doc_id, source_filename=source_filename)

        # Step 2: формируем embedding_text из текущего чанка и контекста соседей.
        cw = max(0, self.config.context_window)
        for i, chunk in enumerate(chunks):
            prev_ctx = chunks[i - 1].text[-cw:] if i > 0 and cw > 0 else ""
            next_ctx = chunks[i + 1].text[:cw] if i < len(chunks) - 1 and cw > 0 else ""
            parts = [p for p in [prev_ctx, chunk.text, next_ctx] if p]
            chunk.embedding_text = " ".join(parts) if len(parts) > 1 else None

        return chunks
