"""CRUD-операции с документами и их метаданными в БД ноутбука."""
# --- Imports ---
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..embedding_service import EmbeddedChunk
from ..parse_service import DocumentMetadata


# --- Functions ---
def upsert_document(
    conn: sqlite3.Connection,
    metadata: DocumentMetadata,
    embedded_chunks: list[EmbeddedChunk],
    tags: list[str] | None = None,
    is_enabled: bool = True,
    index_error: str | None = None,
) -> None:
    """Перезаписывает документ целиком: метаданные, чанки, FTS и эмбеддинги."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO documents (
            doc_id, source_id, filename, filepath, file_hash, size_bytes,
            title, authors, year, source, is_enabled, is_indexed, index_error,
            created_at, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            source_id=excluded.source_id,
            filename=excluded.filename,
            filepath=excluded.filepath,
            file_hash=excluded.file_hash,
            size_bytes=excluded.size_bytes,
            title=excluded.title,
            authors=excluded.authors,
            year=excluded.year,
            source=excluded.source,
            is_enabled=excluded.is_enabled,
            is_indexed=excluded.is_indexed,
            index_error=excluded.index_error,
            indexed_at=excluded.indexed_at
        """,
        (
            metadata.doc_id,
            metadata.doc_id,
            metadata.filename,
            metadata.filepath,
            metadata.file_hash,
            metadata.file_size_bytes,
            metadata.title,
            json.dumps(metadata.authors or [], ensure_ascii=False),
            metadata.year,
            metadata.source,
            1 if is_enabled else 0,
            1 if index_error is None else 2,
            index_error,
            now,
            now,
        ),
    )

    conn.execute("DELETE FROM chunk_embeddings WHERE chunk_rowid IN (SELECT rowid FROM chunks WHERE doc_id=?)", (metadata.doc_id,))
    conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT rowid FROM chunks WHERE doc_id=?)", (metadata.doc_id,))
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (metadata.doc_id,))

    for item in embedded_chunks:
        chunk = item.parsed_chunk
        chunk_id = chunk.get("chunk_id") or f"{metadata.doc_id}:{chunk.get('chunk_index', 0)}"
        cursor = conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, doc_id, chunk_index, page_number, chunk_type,
                section_header, parent_header, chunk_text, is_enabled, token_count,
                embedding_text, parent_chunk_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                metadata.doc_id,
                int(chunk.get("chunk_index", 0)),
                chunk.get("page_number"),
                str(chunk.get("chunk_type") or chunk.get("type") or "text"),
                chunk.get("section_header"),
                chunk.get("parent_header"),
                chunk.get("text", ""),
                1,
                int(getattr(item.meta, "token_count", 0)),
                chunk.get("embedding_text"),
                chunk.get("parent_chunk_id"),
            ),
        )
        rowid = int(cursor.lastrowid)
        conn.execute("INSERT INTO chunks_fts(rowid, chunk_text) VALUES (?, ?)", (rowid, chunk.get("text", "")))
        conn.execute(
            "INSERT OR REPLACE INTO chunk_embeddings(chunk_rowid, embedding) VALUES (?, ?)",
            (rowid, json.dumps(item.embedding, ensure_ascii=False)),
        )

    _set_document_tags(conn, metadata.doc_id, tags or metadata.tags)
    conn.commit()


def set_document_enabled(conn: sqlite3.Connection, doc_id: str, enabled: bool) -> None:
    """Включает или отключает документ в поиске."""
    conn.execute("UPDATE documents SET is_enabled=? WHERE doc_id=?", (1 if enabled else 0, doc_id))
    conn.commit()


def set_document_tags(conn: sqlite3.Connection, doc_id: str, tags: list[str]) -> None:
    """Перезаписывает теги документа."""
    _set_document_tags(conn, doc_id, tags)
    conn.commit()


def set_tag_enabled(conn: sqlite3.Connection, tag: str, enabled: bool) -> None:
    """Включает или отключает тег фильтрации."""
    conn.execute("INSERT OR IGNORE INTO tags(tag, is_enabled) VALUES (?, 1)", (tag,))
    conn.execute("UPDATE tags SET is_enabled=? WHERE tag=?", (1 if enabled else 0, tag))
    conn.commit()


def _set_document_tags(conn: sqlite3.Connection, doc_id: str, tags: list[str]) -> None:
    # Перезаписываем теги: удаляем старые и вставляем новые
    conn.execute("DELETE FROM document_tags WHERE doc_id=?", (doc_id,))
    for tag in sorted(set(tags)):
        conn.execute("INSERT OR IGNORE INTO tags(tag, is_enabled) VALUES (?, 1)", (tag,))
        conn.execute("INSERT OR IGNORE INTO document_tags(doc_id, tag) VALUES (?, ?)", (doc_id, tag))
