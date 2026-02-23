"""Оркестратор парсинга документов: связывает экстрактор, чанкер и сериализатор."""
# --- Imports ---
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .chunkers import get_chunker
from .extractors import get_extractor
from .models import ChunkType, DocumentMetadata, ParsedChunk, ParserConfig, UnsupportedFormatError
from .serializer import save_parsing_result
from .utils import _token_count


# --- Models / Classes ---
class DocumentParser:
    """Тонкий оркестратор: выбирает экстрактор → чанкер → сохраняет результат."""

    def __init__(self, config: ParserConfig):
        self.config = config

    def parse(
        self,
        filepath: str,
        notebook_id: str,
        metadata_override: Optional[dict] = None,
    ) -> tuple[DocumentMetadata, list[ParsedChunk]]:
        """Полный пайплайн парсинга документа.

        Этапы:
        1) извлечение сырых блоков из файла;
        2) разбиение на чанки выбранным методом;
        3) сбор метаданных;
        4) сохранение результата в ``CHUNKS_DIR``.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(path)

        # Внешний слой может передать фиксированный doc_id и индивидуальные настройки.
        metadata_override = metadata_override or {}
        suffix = path.suffix.lower()

        # На этом этапе получаем унифицированные блоки, независимо от формата файла.
        if suffix == ".xlsx":
            blocks = [{
                "text": f"Table content placeholder for {path.name}",
                "chunk_type": ChunkType.TABLE,
                "page_number": 1,
                "section_header": None,
                "parent_header": None,
            }]
            total_pages = 1
        elif suffix in {".html", ".epub"}:
            raise UnsupportedFormatError(f"Format planned but not implemented yet: {suffix}")
        else:
            extractor = get_extractor(suffix, self.config)
            blocks, total_pages = extractor.extract(path)

        doc_id = str(metadata_override.get("doc_id") or uuid4())
        # Далее блоки маршрутизируются в выбранный алгоритм чанкинга.
        chunker = get_chunker(self.config)
        chunks = chunker.chunk(blocks, doc_id=doc_id, source_filename=path.name)

        metadata = DocumentMetadata(
            doc_id=doc_id,
            notebook_id=notebook_id,
            filename=path.name,
            filepath=str(path),
            file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
            file_size_bytes=path.stat().st_size,
            title=metadata_override.get("title"),
            authors=metadata_override.get("authors"),
            year=metadata_override.get("year"),
            source=metadata_override.get("source"),
            total_pages=total_pages,
            total_chunks=len(chunks),
            language=self.detect_language("\n".join(block["text"] for block in blocks)[:1000]),
            parser_version="1.1.0",
            parsed_at=datetime.now(timezone.utc).isoformat(),
            individual_config=metadata_override.get("individual_config")
            or {
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
            },
            is_enabled=bool(metadata_override.get("is_enabled", True)),
            chunking_method=self.config.chunking_method,
        )
        # Сохраняем промежуточный JSON, который затем потребляет embedding_service.
        save_parsing_result(notebook_id, metadata, chunks)
        return metadata, chunks

    def detect_language(self, text_sample: str) -> str:
        """Определяет язык документа для метаданных; при ошибке возвращает ``unknown``."""
        if not text_sample.strip():
            return "unknown"
        try:
            from langdetect import detect
            return detect(text_sample)
        except Exception:
            return "unknown"

    def estimate_chunks_count(self, filepath: str) -> int:
        """Оценивает количество чанков без полного парсинга."""
        path = Path(filepath)
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return 1
        elif suffix in {".html", ".epub"}:
            return 0
        else:
            extractor = get_extractor(suffix, self.config)
            blocks, _ = extractor.extract(path)
        total_tokens = sum(_token_count(block["text"]) for block in blocks)
        return max(1, total_tokens // max(1, self.config.chunk_size) + 1)

    def save_parsing_result(self, notebook_id: str, metadata: DocumentMetadata, chunks: list[ParsedChunk]) -> str:
        """Сериализует метаданные и чанки в JSON-файл промежуточного слоя."""
        return save_parsing_result(notebook_id, metadata, chunks)

    def load_parsing_result(self, notebook_id: str, doc_id: str) -> tuple[DocumentMetadata, list[ParsedChunk]]:
        """Загружает и десериализует результат парсинга из JSON-файла."""
        from .serializer import load_parsing_result as _load
        return _load(notebook_id, doc_id)
