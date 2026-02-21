"""SQLite storage for notebook documents/chunks/embeddings and search."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import NOTEBOOKS_DB_DIR
from .embedding_service import EmbeddedChunk
from .parse_service import DocumentMetadata


class NotebookDB:
    def __init__(self, notebook_id: str):
        self.notebook_id = notebook_id
        NOTEBOOKS_DB_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = NOTEBOOKS_DB_DIR / f"{notebook_id}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._configure()
        self._migrate()

    def _configure(self) -> None:
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA cache_size=-64000")

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                filename TEXT,
                filepath TEXT,
                file_hash TEXT,
                size_bytes INTEGER,
                title TEXT,
                authors TEXT,
                year INTEGER,
                source TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                is_indexed INTEGER NOT NULL DEFAULT 1,
                index_error TEXT,
                created_at TEXT,
                indexed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                page_number INTEGER,
                chunk_type TEXT,
                section_header TEXT,
                parent_header TEXT,
                chunk_text TEXT NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                token_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_text,
                content='chunks',
                content_rowid='rowid'
            );

            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_rowid INTEGER PRIMARY KEY,
                embedding TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                tag TEXT PRIMARY KEY,
                is_enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS document_tags (
                doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                tag TEXT NOT NULL REFERENCES tags(tag) ON DELETE CASCADE,
                PRIMARY KEY(doc_id, tag)
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            CREATE INDEX IF NOT EXISTS idx_documents_enabled ON documents(is_enabled);
            """
        )
        fk_rows = self.conn.execute("PRAGMA foreign_key_list(chunk_embeddings)").fetchall()
        if fk_rows:
            self.conn.execute("DROP TABLE IF EXISTS chunk_embeddings")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_rowid INTEGER PRIMARY KEY,
                    embedding TEXT NOT NULL
                )
                """
            )
        self.conn.commit()

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
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
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

        self.conn.execute("DELETE FROM chunk_embeddings WHERE chunk_rowid IN (SELECT rowid FROM chunks WHERE doc_id=?)", (metadata.doc_id,))
        self.conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT rowid FROM chunks WHERE doc_id=?)", (metadata.doc_id,))
        self.conn.execute("DELETE FROM chunks WHERE doc_id=?", (metadata.doc_id,))

        for item in embedded_chunks:
            chunk = item.parsed_chunk
            chunk_id = chunk.get("chunk_id") or f"{metadata.doc_id}:{chunk.get('chunk_index', 0)}"
            cursor = self.conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, doc_id, chunk_index, page_number, chunk_type,
                    section_header, parent_header, chunk_text, is_enabled, token_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            rowid = int(cursor.lastrowid)
            self.conn.execute("INSERT INTO chunks_fts(rowid, chunk_text) VALUES (?, ?)", (rowid, chunk.get("text", "")))
            self.conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings(chunk_rowid, embedding) VALUES (?, ?)",
                (rowid, json.dumps(item.embedding, ensure_ascii=False)),
            )

        self._set_document_tags(metadata.doc_id, tags or metadata.tags)
        self.conn.commit()

    def set_document_enabled(self, doc_id: str, enabled: bool) -> None:
        self.conn.execute("UPDATE documents SET is_enabled=? WHERE doc_id=?", (1 if enabled else 0, doc_id))
        self.conn.commit()

    def _set_document_tags(self, doc_id: str, tags: list[str]) -> None:
        self.conn.execute("DELETE FROM document_tags WHERE doc_id=?", (doc_id,))
        for tag in sorted(set(tags)):
            self.conn.execute("INSERT OR IGNORE INTO tags(tag, is_enabled) VALUES (?, 1)", (tag,))
            self.conn.execute("INSERT OR IGNORE INTO document_tags(doc_id, tag) VALUES (?, ?)", (doc_id, tag))

    def set_document_tags(self, doc_id: str, tags: list[str]) -> None:
        self._set_document_tags(doc_id, tags)
        self.conn.commit()

    def set_tag_enabled(self, tag: str, enabled: bool) -> None:
        self.conn.execute("INSERT OR IGNORE INTO tags(tag, is_enabled) VALUES (?, 1)", (tag,))
        self.conn.execute("UPDATE tags SET is_enabled=? WHERE tag=?", (1 if enabled else 0, tag))
        self.conn.commit()

    def _enabled_filter_clause(self, selected_source_ids: list[str] | None, only_enabled_tags: bool) -> tuple[str, list[Any]]:
        where = ["d.is_enabled=1", "c.is_enabled=1"]
        params: list[Any] = []
        if selected_source_ids:
            placeholders = ",".join("?" for _ in selected_source_ids)
            where.append(f"d.doc_id IN ({placeholders})")
            params.extend(selected_source_ids)
        if only_enabled_tags:
            where.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM document_tags dt
                    JOIN tags t ON t.tag=dt.tag
                    WHERE dt.doc_id=d.doc_id AND t.is_enabled=0
                )
                """
            )
        return " AND ".join(where), params

    def search_fts(self, query: str, top_k: int, selected_source_ids: list[str] | None = None, only_enabled_tags: bool = True) -> list[dict[str, Any]]:
        where_clause, params = self._enabled_filter_clause(selected_source_ids, only_enabled_tags)
        rows = self.conn.execute(
            f"""
            SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
                   d.filepath, d.filename, bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.rowid=chunks_fts.rowid
            JOIN documents d ON d.doc_id=c.doc_id
            WHERE chunks_fts MATCH ? AND {where_clause}
            ORDER BY score
            LIMIT ?
            """,
            [query, *params, top_k],
        ).fetchall()
        if rows:
            return [dict(row) for row in rows]

        terms = [term for term in query.strip().split() if term]
        if not terms:
            return []
        like_clauses = " OR ".join(["c.chunk_text LIKE ?" for _ in terms])
        like_values = [f"%{term}%" for term in terms]
        fallback_rows = self.conn.execute(
            f"""
            SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
                   d.filepath, d.filename, 0.0 AS score
            FROM chunks c
            JOIN documents d ON d.doc_id=c.doc_id
            WHERE ({like_clauses}) AND {where_clause}
            LIMIT ?
            """,
            [*like_values, *params, top_k],
        ).fetchall()
        if fallback_rows:
            return [dict(row) for row in fallback_rows]

        generic_rows = self.conn.execute(
            f"""
            SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
                   d.filepath, d.filename, 0.0 AS score
            FROM chunks c
            JOIN documents d ON d.doc_id=c.doc_id
            WHERE {where_clause}
            ORDER BY c.rowid DESC
            LIMIT ?
            """,
            [*params, top_k],
        ).fetchall()
        return [dict(row) for row in generic_rows]

    def search_vector(self, query_vector: list[float], top_k: int, selected_source_ids: list[str] | None = None, only_enabled_tags: bool = True) -> list[dict[str, Any]]:
        where_clause, params = self._enabled_filter_clause(selected_source_ids, only_enabled_tags)
        rows = self.conn.execute(
            f"""
            SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
                   d.filepath, d.filename, ce.embedding
            FROM chunk_embeddings ce
            JOIN chunks c ON c.rowid=ce.chunk_rowid
            JOIN documents d ON d.doc_id=c.doc_id
            WHERE {where_clause}
            """,
            params,
        ).fetchall()

        q_norm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
        scored: list[dict[str, Any]] = []
        for row in rows:
            vec = [float(x) for x in json.loads(row["embedding"])]
            vec_norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            score = float(sum(a * b for a, b in zip(vec, query_vector)) / (vec_norm * q_norm))
            item = dict(row)
            item["score"] = score
            scored.append(item)

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]


def db_for_notebook(notebook_id: str) -> NotebookDB:
    return NotebookDB(notebook_id)
