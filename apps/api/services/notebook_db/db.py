"""NotebookDB — оркестратор: инициализация соединения и делегирование операций."""
# --- Imports ---
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ...config import NOTEBOOKS_DB_DIR
from ..embedding_service import EmbeddedChunk
from ..parse_service import DocumentMetadata
from . import documents as _docs
from . import schema as _schema
from . import search as _search


# --- Models / Classes ---
class NotebookDB:
    """Локальная БД ноутбука: документы, чанки, индексы и теги фильтрации."""

    def __init__(self, notebook_id: str):
        self.notebook_id = notebook_id
        NOTEBOOKS_DB_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = NOTEBOOKS_DB_DIR / f"{notebook_id}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        _schema.configure_connection(self.conn)
        _schema.migrate(self.conn)

    def close(self) -> None:
        self.conn.close()

    def upsert_document(
        self,
        metadata: DocumentMetadata,
        embedded_chunks: list[EmbeddedChunk],
        tags: list[str] | None = None,
        is_enabled: bool = True,
        index_error: str | None = None,
    ) -> None:
        """Перезаписывает документ целиком: метаданные, чанки, FTS и эмбеддинги."""
        _docs.upsert_document(self.conn, metadata, embedded_chunks, tags, is_enabled, index_error)

    def set_document_enabled(self, doc_id: str, enabled: bool) -> None:
        _docs.set_document_enabled(self.conn, doc_id, enabled)

    def set_document_tags(self, doc_id: str, tags: list[str]) -> None:
        _docs.set_document_tags(self.conn, doc_id, tags)

    def set_tag_enabled(self, tag: str, enabled: bool) -> None:
        _docs.set_tag_enabled(self.conn, tag, enabled)

    def search_fts(
        self,
        query: str,
        top_k: int,
        selected_source_ids: list[str] | None = None,
        only_enabled_tags: bool = True,
    ) -> list[dict[str, Any]]:
        """Полнотекстовый поиск с fallback на LIKE и общий резервный список."""
        return _search.search_fts(self.conn, query, top_k, selected_source_ids, only_enabled_tags)

    def search_vector(
        self,
        query_vector: list[float],
        top_k: int,
        selected_source_ids: list[str] | None = None,
        only_enabled_tags: bool = True,
    ) -> list[dict[str, Any]]:
        """Векторный поиск по cosine similarity поверх сохраненных embedding JSON."""
        return _search.search_vector(self.conn, query_vector, top_k, selected_source_ids, only_enabled_tags)


# --- Functions ---
def db_for_notebook(notebook_id: str) -> NotebookDB:
    """Создаёт и возвращает экземпляр NotebookDB для заданного ноутбука."""
    return NotebookDB(notebook_id)
