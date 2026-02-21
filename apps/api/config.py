"""Runtime configuration for API defaults."""

from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
CHUNKS_DIR = DATA_DIR / "parsing"
NOTEBOOKS_DB_DIR = DATA_DIR / "notebooks"
LOGS_DIR = DATA_DIR / "logs"

EMBEDDING_ENABLED = os.getenv("EMBEDDING_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")
EMBEDDING_ENDPOINT = os.getenv("EMBEDDING_ENDPOINT") or None
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434").rstrip("/")

MAX_UPLOAD_MB = 25
UPLOAD_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
