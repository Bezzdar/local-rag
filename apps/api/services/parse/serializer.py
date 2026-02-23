"""Сериализация и десериализация результатов парсинга в JSON-файлы промежуточного слоя."""
# --- Imports ---
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ...config import CHUNKS_DIR
from .models import ChunkType, DocumentMetadata, ParsedChunk


# --- Functions ---
def save_parsing_result(notebook_id: str, metadata: DocumentMetadata, chunks: list[ParsedChunk]) -> str:
    """Сериализует метаданные и чанки в JSON-файл промежуточного слоя."""
    target_dir = CHUNKS_DIR / notebook_id
    target_dir.mkdir(parents=True, exist_ok=True)
    output = target_dir / f"{metadata.doc_id}.json"
    payload = {
        "metadata": asdict(metadata),
        "chunks": [{**asdict(chunk), "chunk_type": chunk.chunk_type.value} for chunk in chunks],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def load_parsing_result(notebook_id: str, doc_id: str) -> tuple[DocumentMetadata, list[ParsedChunk]]:
    """Загружает и десериализует результат парсинга из JSON-файла."""
    path = CHUNKS_DIR / notebook_id / f"{doc_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = DocumentMetadata(**payload["metadata"])
    chunks = [ParsedChunk(**{**item, "chunk_type": ChunkType(item["chunk_type"])}) for item in payload["chunks"]]
    return metadata, chunks
