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
    """Thread-safe SQLite persistence for notebooks, sources, and parsing settings.

    Слой хранит только глобальное состояние проекта (ноутбуки/источники/настройки),
    а контент чанков и эмбеддинги лежат в per-notebook БД.
    """

    def __init__(self, db_path: Path = GLOBAL_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def _migrate(self) -> None:
        """Создание схемы и безопасные ALTER-миграции для старых инсталляций."""
        with self._lock:
            # Create tables first (full schema) — idempotent for new installations
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
                    individual_config TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS parsing_settings (
                    notebook_id TEXT PRIMARY KEY,
                    chunk_size INTEGER NOT NULL DEFAULT 512,
                    chunk_overlap INTEGER NOT NULL DEFAULT 64,
                    min_chunk_size INTEGER NOT NULL DEFAULT 50,
                    ocr_enabled INTEGER NOT NULL DEFAULT 1,
                    ocr_language TEXT NOT NULL DEFAULT 'rus+eng',
                    auto_parse_on_upload INTEGER NOT NULL DEFAULT 0,
                    chunking_method TEXT NOT NULL DEFAULT 'general',
                    context_window INTEGER NOT NULL DEFAULT 128,
                    use_llm_summary INTEGER NOT NULL DEFAULT 0,
                    doc_type TEXT NOT NULL DEFAULT 'technical_manual',
                    parent_chunk_size INTEGER NOT NULL DEFAULT 1024,
                    child_chunk_size INTEGER NOT NULL DEFAULT 128,
                    symbol_separator TEXT NOT NULL DEFAULT '---chunk---'
                );
                """
            )
            # ALTER TABLE for older databases that already exist without the new columns
            _alter_statements = [
                "ALTER TABLE parsing_settings ADD COLUMN auto_parse_on_upload INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE parsing_settings ADD COLUMN chunking_method TEXT NOT NULL DEFAULT 'general'",
                "ALTER TABLE parsing_settings ADD COLUMN context_window INTEGER NOT NULL DEFAULT 128",
                "ALTER TABLE parsing_settings ADD COLUMN use_llm_summary INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE parsing_settings ADD COLUMN doc_type TEXT NOT NULL DEFAULT 'technical_manual'",
                "ALTER TABLE parsing_settings ADD COLUMN parent_chunk_size INTEGER NOT NULL DEFAULT 1024",
                "ALTER TABLE parsing_settings ADD COLUMN child_chunk_size INTEGER NOT NULL DEFAULT 128",
                "ALTER TABLE parsing_settings ADD COLUMN symbol_separator TEXT NOT NULL DEFAULT '---chunk---'",
                "ALTER TABLE sources ADD COLUMN has_base INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE sources ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
            ]
            for _sql in _alter_statements:
                try:
                    self._conn.execute(_sql)
                    self._conn.commit()
                except Exception:
                    pass  # Column already exists

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
        """Создает/обновляет запись источника вместе с индивидуальной конфигурацией."""
        indiv = src.get("individual_config")
        indiv_json = json.dumps(indiv, ensure_ascii=False) if indiv is not None else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sources (
                    id, notebook_id, filename, file_path, file_type, size_bytes, status,
                    added_at, is_enabled, has_docs, has_parsing, has_base, embeddings_status, index_warning, individual_config, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename, file_path=excluded.file_path,
                    file_type=excluded.file_type, size_bytes=excluded.size_bytes,
                    status=excluded.status, is_enabled=excluded.is_enabled,
                    has_docs=excluded.has_docs, has_parsing=excluded.has_parsing,
                    has_base=excluded.has_base,
                    embeddings_status=excluded.embeddings_status,
                    index_warning=excluded.index_warning, individual_config=excluded.individual_config,
                    sort_order=excluded.sort_order
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
                    src.get("sort_order", 0),
                ),
            )
            self._conn.commit()

    def get_max_sort_order(self, notebook_id: str) -> int:
        """Return the current maximum sort_order for sources in a notebook."""
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(sort_order) FROM sources WHERE notebook_id=?", (notebook_id,)
            ).fetchone()
        val = row[0] if row and row[0] is not None else 0
        return int(val)

    def reorder_sources(self, notebook_id: str, ordered_ids: list[str]) -> None:
        """Set sort_order for sources in notebook according to the given ordered list of IDs."""
        with self._lock:
            for idx, source_id in enumerate(ordered_ids, start=1):
                self._conn.execute(
                    "UPDATE sources SET sort_order=? WHERE id=? AND notebook_id=?",
                    (idx, source_id, notebook_id),
                )
            self._conn.commit()

    def renumber_sort_orders(self, notebook_id: str) -> None:
        """Re-assign sequential sort_orders (1..N) to remaining sources after a deletion."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM sources WHERE notebook_id=? ORDER BY sort_order, added_at",
                (notebook_id,),
            ).fetchall()
            for idx, row in enumerate(rows, start=1):
                self._conn.execute("UPDATE sources SET sort_order=? WHERE id=?", (idx, row[0]))
            self._conn.commit()

    def load_all_sources(self) -> list[dict[str, Any]]:
        """Читает источники и нормализует типы/дефолты для API-слоя."""
        _default_config: dict[str, Any] = {
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
        }
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sources ORDER BY sort_order, added_at").fetchall()
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
            d["sort_order"] = int(d.get("sort_order") or 0)
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
        chunking_method: str = "general",
        context_window: int = 128,
        use_llm_summary: bool = False,
        doc_type: str = "technical_manual",
        parent_chunk_size: int = 1024,
        child_chunk_size: int = 128,
        symbol_separator: str = "---chunk---",
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO parsing_settings
                    (notebook_id, chunk_size, chunk_overlap, min_chunk_size, ocr_enabled, ocr_language,
                     auto_parse_on_upload, chunking_method, context_window, use_llm_summary,
                     doc_type, parent_chunk_size, child_chunk_size, symbol_separator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(notebook_id) DO UPDATE SET
                    chunk_size=excluded.chunk_size, chunk_overlap=excluded.chunk_overlap,
                    min_chunk_size=excluded.min_chunk_size, ocr_enabled=excluded.ocr_enabled,
                    ocr_language=excluded.ocr_language, auto_parse_on_upload=excluded.auto_parse_on_upload,
                    chunking_method=excluded.chunking_method, context_window=excluded.context_window,
                    use_llm_summary=excluded.use_llm_summary, doc_type=excluded.doc_type,
                    parent_chunk_size=excluded.parent_chunk_size, child_chunk_size=excluded.child_chunk_size,
                    symbol_separator=excluded.symbol_separator
                """,
                (
                    notebook_id, chunk_size, chunk_overlap, min_chunk_size,
                    1 if ocr_enabled else 0, ocr_language, 1 if auto_parse_on_upload else 0,
                    chunking_method, context_window, 1 if use_llm_summary else 0,
                    doc_type, parent_chunk_size, child_chunk_size, symbol_separator,
                ),
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
            d["use_llm_summary"] = bool(d.get("use_llm_summary", 0))
            d.setdefault("chunking_method", "general")
            d.setdefault("context_window", 128)
            d.setdefault("doc_type", "technical_manual")
            d.setdefault("parent_chunk_size", 1024)
            d.setdefault("child_chunk_size", 128)
            d.setdefault("symbol_separator", "---chunk---")
            result.append(d)
        return result

    def delete_source(self, source_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
            self._conn.commit()
