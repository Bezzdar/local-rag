"""Persistent SQLite store for notebooks, sources, and parsing settings."""

# --- Imports ---
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

GLOBAL_DB_PATH = DATA_DIR / "store.db"


# --- Основные блоки ---
class GlobalDB:
    """Thread-safe SQLite persistence for notebooks, sources, and parsing settings."""

    def __init__(self, db_path: Path = GLOBAL_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            # Add missing columns for older databases
            try:
                self._conn.execute("ALTER TABLE parsing_settings ADD COLUMN auto_parse_on_upload INTEGER NOT NULL DEFAULT 0")
                self._conn.commit()
            except Exception:
                pass  # Column already exists
            try:
                self._conn.execute("ALTER TABLE sources ADD COLUMN has_base INTEGER NOT NULL DEFAULT 0")
                self._conn.commit()
            except Exception:
                pass  # Column already exists
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS notebooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL DEFAULT 'other',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'new',
                    added_at TEXT NOT NULL,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    has_docs INTEGER NOT NULL DEFAULT 1,
                    has_parsing INTEGER NOT NULL DEFAULT 0,
                    has_base INTEGER NOT NULL DEFAULT 0,
                    embeddings_status TEXT NOT NULL DEFAULT 'unavailable',
                    index_warning TEXT,
                    individual_config TEXT
                );

                CREATE TABLE IF NOT EXISTS parsing_settings (
                    notebook_id TEXT PRIMARY KEY,
                    chunk_size INTEGER NOT NULL DEFAULT 512,
                    chunk_overlap INTEGER NOT NULL DEFAULT 64,
                    min_chunk_size INTEGER NOT NULL DEFAULT 50,
                    ocr_enabled INTEGER NOT NULL DEFAULT 1,
                    ocr_language TEXT NOT NULL DEFAULT 'rus+eng',
                    auto_parse_on_upload INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    # --- Notebooks ---

    def upsert_notebook(self, id: str, title: str, created_at: str, updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO notebooks (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at",
                (id, title, created_at, updated_at),
            )
            self._conn.commit()

    def delete_notebook(self, notebook_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE notebook_id=?", (notebook_id,))
            self._conn.execute("DELETE FROM parsing_settings WHERE notebook_id=?", (notebook_id,))
            self._conn.execute("DELETE FROM notebooks WHERE id=?", (notebook_id,))
            self._conn.commit()

    def load_all_notebooks(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM notebooks ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    # --- Sources ---

    def upsert_source(self, src: dict[str, Any]) -> None:
        indiv = src.get("individual_config")
        indiv_json = json.dumps(indiv, ensure_ascii=False) if indiv is not None else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sources (
                    id, notebook_id, filename, file_path, file_type, size_bytes, status,
                    added_at, is_enabled, has_docs, has_parsing, has_base, embeddings_status, index_warning, individual_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename, file_path=excluded.file_path,
                    file_type=excluded.file_type, size_bytes=excluded.size_bytes,
                    status=excluded.status, is_enabled=excluded.is_enabled,
                    has_docs=excluded.has_docs, has_parsing=excluded.has_parsing,
                    has_base=excluded.has_base,
                    embeddings_status=excluded.embeddings_status,
                    index_warning=excluded.index_warning, individual_config=excluded.individual_config
                """,
                (
                    src["id"],
                    src["notebook_id"],
                    src["filename"],
                    src["file_path"],
                    src.get("file_type", "other"),
                    src.get("size_bytes", 0),
                    src.get("status", "new"),
                    src["added_at"],
                    1 if src.get("is_enabled", True) else 0,
                    1 if src.get("has_docs", True) else 0,
                    1 if src.get("has_parsing", False) else 0,
                    1 if src.get("has_base", False) else 0,
                    src.get("embeddings_status", "unavailable"),
                    src.get("index_warning"),
                    indiv_json,
                ),
            )
            self._conn.commit()

    def load_all_sources(self) -> list[dict[str, Any]]:
        _default_config: dict[str, Any] = {
            "chunk_size": None,
            "chunk_overlap": None,
            "ocr_enabled": None,
            "ocr_language": None,
        }
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sources ORDER BY added_at").fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            raw_cfg = d.get("individual_config")
            if raw_cfg:
                try:
                    d["individual_config"] = json.loads(raw_cfg)
                except Exception:
                    d["individual_config"] = dict(_default_config)
            else:
                d["individual_config"] = dict(_default_config)
            d["is_enabled"] = bool(d["is_enabled"])
            d["has_docs"] = bool(d["has_docs"])
            d["has_parsing"] = bool(d["has_parsing"])
            d["has_base"] = bool(d.get("has_base", 0))
            result.append(d)
        return result

    # --- Parsing settings ---

    def upsert_parsing_settings(
        self,
        notebook_id: str,
        chunk_size: int,
        chunk_overlap: int,
        min_chunk_size: int,
        ocr_enabled: bool,
        ocr_language: str,
        auto_parse_on_upload: bool = False,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO parsing_settings
                    (notebook_id, chunk_size, chunk_overlap, min_chunk_size, ocr_enabled, ocr_language, auto_parse_on_upload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(notebook_id) DO UPDATE SET
                    chunk_size=excluded.chunk_size, chunk_overlap=excluded.chunk_overlap,
                    min_chunk_size=excluded.min_chunk_size, ocr_enabled=excluded.ocr_enabled,
                    ocr_language=excluded.ocr_language, auto_parse_on_upload=excluded.auto_parse_on_upload
                """,
                (notebook_id, chunk_size, chunk_overlap, min_chunk_size, 1 if ocr_enabled else 0, ocr_language, 1 if auto_parse_on_upload else 0),
            )
            self._conn.commit()

    def load_all_parsing_settings(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM parsing_settings").fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            d["ocr_enabled"] = bool(d["ocr_enabled"])
            d["auto_parse_on_upload"] = bool(d.get("auto_parse_on_upload", 0))
            result.append(d)
        return result

    def delete_source(self, source_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
            self._conn.commit()
