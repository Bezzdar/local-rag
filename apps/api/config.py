"""Runtime configuration for API defaults."""

# --- Imports ---
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
PARSING_DIR = DATA_DIR / "parsing"
BASE_DIR = DATA_DIR / "base"
INDEX_DIR = BASE_DIR
CHUNKS_DIR = PARSING_DIR

MAX_UPLOAD_MB = 25
UPLOAD_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
