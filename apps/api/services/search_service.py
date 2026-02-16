from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PACKAGES_ROOT = ROOT / "packages"
if str(PACKAGES_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGES_ROOT))

from .index_service import get_notebook_blocks

core_run_fast_search = None


def _query_to_groups(query: str) -> dict[str, list[str]]:
    terms = [token for token in re.findall(r"[\w\-]+", query.lower()) if len(token) > 1]
    return {"AND": terms[:6], "OR": [], "NOT": []}


def search(notebook_id: str, message: str, selected_source_ids: list[str], top_n: int = 5) -> list[dict[str, Any]]:
    chunks = get_notebook_blocks(notebook_id)
    if selected_source_ids:
        chunks = [chunk for chunk in chunks if chunk.get("source_id") in selected_source_ids]

    if not chunks:
        return []

    query = _query_to_groups(message)

    if core_run_fast_search is not None:
        try:
            return core_run_fast_search(query, chunks, top_n=top_n)
        except Exception:
            pass

    needle = message.lower()
    ranked = sorted(chunks, key=lambda item: (needle in item.get("text", "").lower(), len(item.get("text", ""))), reverse=True)
    return ranked[:top_n]


def chunk_to_citation_fields(chunk: dict[str, Any]) -> tuple[str, int | None, str | None]:
    filename = Path(chunk.get("source", "")).name or "unknown"
    page = chunk.get("page")
    section = chunk.get("section_title") or chunk.get("section_id")
    return filename, page if isinstance(page, int) else None, section
