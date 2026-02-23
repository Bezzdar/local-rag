"""Сервис retrieval-поиска и подготовки цитат."""

# --- Imports ---
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .embedding_service import EmbeddingConfig, EmbeddingEngine, EmbeddingProviderConfig
from ..config import EMBEDDING_BASE_URL, EMBEDDING_DIM, EMBEDDING_ENABLED, EMBEDDING_ENDPOINT, EMBEDDING_PROVIDER
from .notebook_db import db_for_notebook

_ENGINE: EmbeddingEngine | None = None
# Глобальный singleton движка: лениво инициализируется, может быть пересоздан через reconfigure_engine.
_OVERRIDE_PROVIDER: str | None = None
_OVERRIDE_BASE_URL: str | None = None
_OVERRIDE_MODEL: str | None = None


# --- Основные блоки ---
def reconfigure_engine(provider: str, base_url: str, model_name: str) -> None:
    """Сбросить движок и применить новые настройки эмбеддинга."""
    global _ENGINE, _OVERRIDE_PROVIDER, _OVERRIDE_BASE_URL, _OVERRIDE_MODEL
    _OVERRIDE_PROVIDER = provider
    _OVERRIDE_BASE_URL = base_url
    _OVERRIDE_MODEL = model_name
    _ENGINE = None


def _engine() -> EmbeddingEngine | None:
    """Ленивая фабрика EmbeddingEngine с учетом runtime-переопределений."""
    global _ENGINE
    if _ENGINE is None:
        try:
            provider = _OVERRIDE_PROVIDER or EMBEDDING_PROVIDER
            base_url = _OVERRIDE_BASE_URL or EMBEDDING_BASE_URL
            model_name = _OVERRIDE_MODEL or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
            _ENGINE = EmbeddingEngine(
                EmbeddingConfig(
                    embedding_dim=EMBEDDING_DIM,
                    provider=EmbeddingProviderConfig(
                        base_url=base_url,
                        model_name=model_name,
                        provider=provider,
                        endpoint=EMBEDDING_ENDPOINT,
                        enabled=EMBEDDING_ENABLED,
                        fallback_dim=EMBEDDING_DIM,
                    )
                )
            )
        except Exception:
            _ENGINE = None
    return _ENGINE


def _rrf_merge(vector_rows: list[dict[str, Any]], fts_rows: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """Сливает vector+FTS выдачу по алгоритму Reciprocal Rank Fusion."""
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
    """Гибридный retrieval: vector + FTS, затем нормализация к общему формату API."""
    notebook_db = db_for_notebook(notebook_id)
    try:
        # 1) Пытаемся поднять embedding engine; если недоступен — продолжаем только через FTS.
        engine = _engine()
        if engine is not None and engine.is_embedding_available:
            # Вектор запроса используется для semantic retrieval в notebook_db.search_vector().
            query_vector = engine.embed_query(message)
            vector_rows = notebook_db.search_vector(
                query_vector=query_vector,
                top_k=max(top_n * 3, 10),
                selected_source_ids=selected_source_ids or None,
                only_enabled_tags=True,
            )
        else:
            vector_rows = []
        try:
            # 2) Параллельно запрашиваем FTS-кандидатов, чтобы покрыть lexical match.
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

    # 3) Если векторов нет — возвращаем FTS, иначе объединяем выдачу через RRF.
    merged = fts_rows[:top_n] if not vector_rows else _rrf_merge(vector_rows, fts_rows, top_n)
    # 4) Приводим записи БД к единому контракту ответа для chat/retrieval API.
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
    """Преобразует retrieval-чанк в поля цитаты (filename/page/section)."""
    filename = Path(chunk.get("source", "")).name or "unknown"
    page = chunk.get("page")
    section = chunk.get("section_title") or chunk.get("section_id")
    return filename, page if isinstance(page, int) else None, section


def normalize_chunk_scores(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Нормализует поле score в чанках к диапазону [0, 1] относительно максимума.

    Если все оценки равны нулю (например, работает только FTS без эмбеддингов),
    всем чанкам присваивается score=1.0, чтобы пороговая фильтрация не отбрасывала
    валидные результаты.
    """
    if not chunks:
        return chunks
    # Нормализация нужна для единых порогов независимо от абсолютной шкалы scorer-а.
    max_score = max(c.get("score", 0.0) for c in chunks)
    if max_score <= 0.0:
        return [{**c, "score": 1.0} for c in chunks]
    return [{**c, "score": c.get("score", 0.0) / max_score} for c in chunks]


def filter_chunks_by_threshold(chunks: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    """Возвращает только чанки с нормализованной оценкой >= threshold."""
    return [c for c in chunks if c.get("score", 0.0) >= threshold]
