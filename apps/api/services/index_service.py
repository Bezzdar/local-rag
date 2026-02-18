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

from .parse_service import extract_blocks

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


async def index_source(notebook_id: str, source_id: str, file_path: str) -> list[dict[str, Any]]:
    """Parse and index one file; optional legacy engine run behind feature flag."""
    path = Path(file_path)
    blocks = extract_blocks(path)

    converted = []
    for block in blocks:
        converted.append(
            {
                "source_id": source_id,
                "source": block.get("source", str(path)),
                "page": block.get("page", 1),
                "section_id": block.get("section_id", "p1.s1"),
                "section_title": block.get("section_title", "__root__"),
                "text": block.get("text", ""),
                "type": block.get("type", "text"),
            }
        )

    notebook_blocks = INDEXED_BLOCKS.setdefault(notebook_id, [])
    notebook_blocks[:] = [item for item in notebook_blocks if item.get("source_id") != source_id]
    notebook_blocks.extend(converted)

    if ENABLE_LEGACY_ENGINE and core_engine is not None:
        try:
            await asyncio.to_thread(core_engine.trigger_indexing, notebook_id)
        except Exception:
            pass

    return converted
