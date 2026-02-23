"""Метод чанкинга General: fixed-size чанки с overlap соседних фрагментов."""
# --- Imports ---
from __future__ import annotations

from typing import Optional

from ..models import ChunkType, ParsedChunk, ParserConfig
from ..utils import _token_count, _tokenize
from .base import BaseChunker


# --- Models / Classes ---
class GeneralChunker(BaseChunker):
    """General-метод: fixed-size чанки + overlap соседних фрагментов."""

    def chunk(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        """Разбивает блоки на чанки фиксированного размера с перекрытием."""
        chunks: list[ParsedChunk] = []
        pending_header: Optional[dict] = None

        # Проходим по потоку блоков и собираем единый список чанков.
        for block in blocks:
            block_type: ChunkType = block["chunk_type"]
            if block_type == ChunkType.HEADER:
                pending_header = block
                continue

            text = block["text"].strip()
            if not text:
                continue

            if pending_header is not None:
                text = f"{pending_header['text']}\n{text}"
                block["section_header"] = pending_header["text"]
                pending_header = None

            if block_type == ChunkType.TABLE:
                chunks.extend(self._chunk_table_block(text, block, doc_id, source_filename, len(chunks)))
                continue

            chunks.extend(self._chunk_text_block(text, block, doc_id, source_filename, len(chunks), block_type))

        # apply overlap metadata only
        # На финальном проходе записываем контекст соседей для retriever/LLM.
        overlap = max(0, self.config.chunk_overlap)
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                chunk.prev_chunk_tail = " ".join(_tokenize(chunks[idx - 1].text)[-overlap:]) if overlap else None
            if idx < len(chunks) - 1:
                chunk.next_chunk_head = " ".join(_tokenize(chunks[idx + 1].text)[:overlap]) if overlap else None

        for idx, chunk in enumerate(chunks):
            chunk.chunk_index = idx
        return chunks

    def _chunk_text_block(
        self,
        text: str,
        block: dict,
        doc_id: str,
        source_filename: str,
        start_index: int,
        chunk_type: ChunkType,
    ) -> list[ParsedChunk]:
        """Нарезает текст токен-окнами; при слишком коротком хвосте объединяет окна."""
        tokens = _tokenize(text)
        if not tokens:
            return []

        out: list[ParsedChunk] = []
        step = max(1, self.config.chunk_size)
        for offset in range(0, len(tokens), step):
            part_tokens = tokens[offset : offset + step]
            part_text = " ".join(part_tokens).strip()
            if _token_count(part_text) < self.config.min_chunk_size and offset + step < len(tokens):
                part_tokens = tokens[offset : offset + (step * 2)]
                part_text = " ".join(part_tokens).strip()
            out.append(
                ParsedChunk(
                    text=part_text,
                    chunk_type=chunk_type,
                    chunk_index=start_index + len(out),
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            )
        return out

    def _chunk_table_block(self, text: str, block: dict, doc_id: str, source_filename: str, start_index: int) -> list[ParsedChunk]:
        """Нарезает таблицу по строкам, дублируя заголовок в каждом куске."""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) <= 2:
            return [
                ParsedChunk(
                    text=text,
                    chunk_type=ChunkType.TABLE,
                    chunk_index=start_index,
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            ]

        header = lines[:2]
        body = lines[2:]
        chunks: list[ParsedChunk] = []
        current_rows: list[str] = []
        for row in body:
            candidate = "\n".join(header + current_rows + [row])
            if _token_count(candidate) > self.config.chunk_size and current_rows:
                chunks.append(
                    ParsedChunk(
                        text="\n".join(header + current_rows),
                        chunk_type=ChunkType.TABLE,
                        chunk_index=start_index + len(chunks),
                        page_number=block.get("page_number"),
                        section_header=block.get("section_header"),
                        parent_header=block.get("parent_header"),
                        prev_chunk_tail=None,
                        next_chunk_head=None,
                        doc_id=doc_id,
                        source_filename=source_filename,
                    )
                )
                current_rows = [row]
                continue
            current_rows.append(row)

        if current_rows:
            chunks.append(
                ParsedChunk(
                    text="\n".join(header + current_rows),
                    chunk_type=ChunkType.TABLE,
                    chunk_index=start_index + len(chunks),
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            )
        return chunks
