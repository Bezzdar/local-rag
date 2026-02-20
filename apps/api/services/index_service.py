"""Сервис сборки и обновления поискового индекса."""

# --- Imports ---
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PACKAGES_ROOT = ROOT / "packages"
if str(PACKAGES_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGES_ROOT))

from .parse_service import DocumentParser, ParserConfig
from .notebook_db import db_for_notebook

try:
    from rag_core.app import engine as core_engine
except Exception:  # noqa: BLE001
    core_engine = None

ENABLE_LEGACY_ENGINE = os.getenv("ENABLE_LEGACY_ENGINE", "0") == "1"


# --- Основные блоки ---
def get_notebook_blocks(notebook_id: str) -> list[dict[str, Any]]:
    notebook_db = db_for_notebook(notebook_id)
    try:
        rows = notebook_db.conn.execute(
            """
            SELECT c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
                   d.filepath
            FROM chunks c
            JOIN documents d ON d.doc_id=c.doc_id
            """
        ).fetchall()
        return [
            {
                "source_id": row["doc_id"],
                "source": row["filepath"],
                "page": row["page_number"],
                "section_id": row["chunk_id"],
                "section_title": row["section_header"] or "__root__",
                "text": row["chunk_text"],
            }
            for row in rows
        ]
    finally:
        notebook_db.close()


def remove_source_blocks(notebook_id: str, source_id: str) -> None:
    return


def clear_notebook_blocks(notebook_id: str) -> None:
    return


async def index_source(
    notebook_id: str,
    source_id: str,
    file_path: str,
    *,
    parser_config: dict[str, Any] | None = None,
    source_state: dict[str, Any] | None = None,
) -> tuple[Any, list[Any]]:
    """Parse one file and return structured metadata/chunks."""
    path = Path(file_path)
    parser = DocumentParser(ParserConfig(**(parser_config or {})))
    metadata, chunks = parser.parse(
        str(path),
        notebook_id,
        metadata_override={
            "doc_id": source_id,
            "individual_config": (source_state or {}).get("individual_config")
            or {
                "chunk_size": None,
                "chunk_overlap": None,
                "ocr_enabled": None,
                "ocr_language": None,
            },
            "is_enabled": (source_state or {}).get("is_enabled", True),
        },
    )

    if ENABLE_LEGACY_ENGINE and core_engine is not None:
        try:
            await asyncio.to_thread(core_engine.trigger_indexing, notebook_id)
        except Exception:
            pass

    return metadata, chunks
