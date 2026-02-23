"""DDL-схема и миграции БД ноутбука: таблицы, индексы, pragma-настройки."""
# --- Imports ---
from __future__ import annotations

import sqlite3


# --- Functions ---
def configure_connection(conn: sqlite3.Connection) -> None:
    """PRAGMA-настройки SQLite и опциональная загрузка sqlite_vec."""
    try:
        import sqlite_vec  # type: ignore[import]
        _has_vec = True
    except Exception:  # noqa: BLE001
        _has_vec = False

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")
    if _has_vec and hasattr(conn, "enable_load_extension"):
        conn.enable_load_extension(True)
        import sqlite_vec as _sv  # type: ignore[import]
        _sv.load(conn)
        conn.enable_load_extension(False)


def migrate(conn: sqlite3.Connection) -> None:
    """Создает таблицы поиска/хранения и выполняет idempotent-миграции."""
    conn.executescript(
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
            token_count INTEGER NOT NULL DEFAULT 0,
            embedding_text TEXT,
            parent_chunk_id TEXT
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
    fk_rows = conn.execute("PRAGMA foreign_key_list(chunk_embeddings)").fetchall()
    if fk_rows:
        conn.execute("DROP TABLE IF EXISTS chunk_embeddings")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_rowid INTEGER PRIMARY KEY,
                embedding TEXT NOT NULL
            )
            """
        )
    # Add new columns to existing databases (idempotent)
    for _sql in [
        "ALTER TABLE chunks ADD COLUMN embedding_text TEXT",
        "ALTER TABLE chunks ADD COLUMN parent_chunk_id TEXT",
    ]:
        try:
            conn.execute(_sql)
        except Exception:
            pass  # Column already exists
    conn.commit()
