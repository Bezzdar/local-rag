"""Сервис сборки и обновления поискового индекса."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .notebook_db import db_for_notebook
from .parse_service import DocumentParser, ParserConfig


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



async def index_source(
    notebook_id: str,
    source_id: str,
    file_path: str,
    *,
    parser_config: dict[str, Any] | None = None,
    source_state: dict[str, Any] | None = None,
) -> tuple[Any, list[Any]]:
    path = Path(file_path)
    parser = DocumentParser(ParserConfig(**(parser_config or {})))
    return parser.parse(
        str(path),
        notebook_id,
        metadata_override={
            "doc_id": source_id,
            "individual_config": (source_state or {}).get("individual_config")
            or {"chunk_size": None, "chunk_overlap": None, "ocr_enabled": None, "ocr_language": None},
            "is_enabled": (source_state or {}).get("is_enabled", True),
        },
    )
