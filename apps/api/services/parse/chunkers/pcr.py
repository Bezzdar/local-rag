"""Метод чанкинга PCR (Parent-Child Retrieval): двухуровневая система чанков."""
# --- Imports ---
from __future__ import annotations

from ..models import ChunkType, ParsedChunk
from ..utils import _tokenize
from .base import BaseChunker


# --- Models / Classes ---
class PCRChunker(BaseChunker):
    """PCR: двухуровневая система. Embed child (маленький), retrieve parent (большой)."""

    def chunk(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        """Разбивает текст на parent-чанки, каждый из которых нарезается на child-чанки."""
        # Build full text from all non-header blocks
        all_text_parts = []
        for block in blocks:
            if block["chunk_type"] != ChunkType.HEADER and block["text"].strip():
                all_text_parts.append(block["text"])
        full_text = "\n".join(all_text_parts)

        parent_step = max(1, self.config.parent_chunk_size)
        child_step = max(1, self.config.child_chunk_size)
        parent_tokens = _tokenize(full_text)

        chunks: list[ParsedChunk] = []
        parent_idx = 0

        # Шаг Parent: создаем крупные смысловые окна для ответа LLM.
        for p_offset in range(0, len(parent_tokens), parent_step):
            parent_token_slice = parent_tokens[p_offset: p_offset + parent_step]
            parent_text = " ".join(parent_token_slice).strip()
            if not parent_text:
                continue

            parent_id = f"{doc_id}:pcr_parent:{parent_idx}"
            child_tokens = _tokenize(parent_text)

            # Шаг Child: режем parent на мелкие фрагменты для векторного поиска.
            for c_offset in range(0, len(child_tokens), child_step):
                child_token_slice = child_tokens[c_offset: c_offset + child_step]
                child_text = " ".join(child_token_slice).strip()
                if not child_text:
                    continue

                chunks.append(ParsedChunk(
                    text=parent_text,          # Full parent: sent to LLM as context
                    embedding_text=child_text, # Small child: used for precise embedding
                    chunk_type=ChunkType.TEXT,
                    chunk_index=len(chunks),
                    page_number=None,
                    section_header=f"Блок {parent_idx + 1}",
                    parent_header=None,
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                    parent_chunk_id=parent_id,
                ))

            parent_idx += 1

        return chunks
