"""Runtime configuration for API defaults."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
INDEX_DIR = DATA_DIR / "index"
CHUNKS_DIR = DATA_DIR / "chunks"

MAX_UPLOAD_MB = 25
UPLOAD_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
