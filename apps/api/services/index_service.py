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

from ..config import BASE_DIR
from .parse_service import DocumentParser, ParserConfig

try:
    from rag_core.app import engine as core_engine
except Exception:  # noqa: BLE001
    core_engine = None

INDEXED_BLOCKS: dict[str, list[dict[str, Any]]] = {}
ENABLE_LEGACY_ENGINE = os.getenv("ENABLE_LEGACY_ENGINE", "0") == "1"


def get_notebook_blocks(notebook_id: str) -> list[dict[str, Any]]:
    return INDEXED_BLOCKS.get(notebook_id, [])


def remove_source_blocks(notebook_id: str, source_id: str) -> None:
    notebook_blocks = INDEXED_BLOCKS.get(notebook_id)
    if not notebook_blocks:
        return
    INDEXED_BLOCKS[notebook_id] = [item for item in notebook_blocks if item.get("source_id") != source_id]


def clear_notebook_blocks(notebook_id: str) -> None:
    INDEXED_BLOCKS.pop(notebook_id, None)


async def index_source(
    notebook_id: str,
    source_id: str,
    file_path: str,
    *,
    parser_config: dict[str, Any] | None = None,
    source_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Parse and index one file; optional legacy engine run behind feature flag."""
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

    converted = []
    for block in chunks:
        converted.append(
            {
                "source_id": source_id,
                "source": str(path),
                "page": block.page_number or 1,
                "section_id": f"p{block.page_number or 1}.s{block.chunk_index + 1}",
                "section_title": block.section_header or "__root__",
                "text": block.text,
                "type": block.chunk_type.value,
                "is_enabled": metadata.is_enabled,
                "doc_id": metadata.doc_id,
            }
        )

    notebook_blocks = INDEXED_BLOCKS.setdefault(notebook_id, [])
    notebook_blocks[:] = [item for item in notebook_blocks if item.get("source_id") != source_id]
    notebook_blocks.extend(converted)

    base_dir = BASE_DIR / notebook_id
    base_dir.mkdir(parents=True, exist_ok=True)
    base_marker = base_dir / f"{source_id}.json"
    base_marker.write_text(str(len(converted)), encoding="utf-8")

    if ENABLE_LEGACY_ENGINE and core_engine is not None:
        try:
            await asyncio.to_thread(core_engine.trigger_indexing, notebook_id)
        except Exception:
            pass

    return converted
