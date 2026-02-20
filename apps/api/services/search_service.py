"""Сервис retrieval-поиска и подготовки цитат."""

# --- Imports ---
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .embedding_service import EmbeddingConfig, EmbeddingEngine, EmbeddingProviderConfig
from .notebook_db import db_for_notebook

_ENGINE: EmbeddingEngine | None = None


# --- Основные блоки ---
def _engine() -> EmbeddingEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = EmbeddingEngine(
            EmbeddingConfig(
                provider=EmbeddingProviderConfig(
                    base_url=os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434"),
                    model_name=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                )
            )
        )
    return _ENGINE


def _rrf_merge(vector_rows: list[dict[str, Any]], fts_rows: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    k = 60
    by_id: dict[str, dict[str, Any]] = {}

    for rank, row in enumerate(vector_rows, start=1):
        key = row["chunk_id"]
        by_id.setdefault(key, {**row, "rrf": 0.0})["rrf"] += 1.0 / (k + rank)

    for rank, row in enumerate(fts_rows, start=1):
        key = row["chunk_id"]
        by_id.setdefault(key, {**row, "rrf": 0.0})["rrf"] += 1.0 / (k + rank)

    merged = sorted(by_id.values(), key=lambda item: item["rrf"], reverse=True)
    return merged[:top_n]


def search(notebook_id: str, message: str, selected_source_ids: list[str], top_n: int = 5) -> list[dict[str, Any]]:
    notebook_db = db_for_notebook(notebook_id)
    try:
        query_vector = _engine().embed_query(message)
        vector_rows = notebook_db.search_vector(
            query_vector=query_vector,
            top_k=max(top_n * 3, 10),
            selected_source_ids=selected_source_ids or None,
            only_enabled_tags=True,
        )
        try:
            fts_rows = notebook_db.search_fts(
                query=message,
                top_k=max(top_n * 3, 10),
                selected_source_ids=selected_source_ids or None,
                only_enabled_tags=True,
            )
        except Exception:
            fts_rows = []
    finally:
        notebook_db.close()

    merged = _rrf_merge(vector_rows, fts_rows, top_n)
    result: list[dict[str, Any]] = []
    for row in merged:
        result.append(
            {
                "source_id": row.get("doc_id"),
                "source": row.get("filepath") or row.get("filename") or "",
                "page": row.get("page_number") or 1,
                "section_id": row.get("chunk_id"),
                "section_title": row.get("section_header") or "__root__",
                "text": row.get("chunk_text", ""),
                "type": "text",
                "doc_id": row.get("doc_id"),
                "score": row.get("rrf", 0.0),
            }
        )
    return result


def chunk_to_citation_fields(chunk: dict[str, Any]) -> tuple[str, int | None, str | None]:
    filename = Path(chunk.get("source", "")).name or "unknown"
    page = chunk.get("page")
    section = chunk.get("section_title") or chunk.get("section_id")
    return filename, page if isinstance(page, int) else None, section
