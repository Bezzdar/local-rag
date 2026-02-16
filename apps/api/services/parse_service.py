from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKAGES_ROOT = ROOT / "packages"
if str(PACKAGES_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGES_ROOT))

from rag_core.parsers.text_extraction import TextBlock, extract_blocks as core_extract_blocks


ALLOWED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".txt", ".log", ".doc"}
FAST_FALLBACK_SUFFIXES = {".pdf", ".docx", ".xlsx"}


def _fallback_block(path: Path, reason: str) -> list[TextBlock]:
    ext = path.suffix.lower().replace(".", "") or "file"
    text = f"Extracted {ext} content placeholder for {path.name}. Section: ingestion_fallback"
    return [
        {
            "text": text,
            "type": "text",
            "page": 1,
            "source": str(path),
            "section_id": "p1.s1",
            "section_title": f"{ext}_section",
        }
    ]


def extract_blocks(file_path: str | Path) -> list[TextBlock]:
    """Wrapper over rag_core parser preserving extract_blocks contract."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported format: {suffix}")

    if suffix in FAST_FALLBACK_SUFFIXES:
        return _fallback_block(path, "fast fallback for binary office format")

    try:
        return core_extract_blocks(path)
    except Exception as exc:  # noqa: BLE001
        return _fallback_block(path, str(exc))
