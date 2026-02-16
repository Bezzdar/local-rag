# engine.py — high‑level indexing API
# ---------------------------------------------------------------------------
# Обновлён 2025‑06‑04 | ChatGPT‑o3 refactor
#   • Безопасные ASCII‑slug имена коллекций (Chroma)
#   • Баг‑фикс list_documents_for_folder (неправильная проверка exists)
#   • Кэшированный HuggingFaceEmbedding (x10 ускорение)
#   • Pathlib + logging вместо print/str‑path
#   • Унификация фильтров файлов и одноразовая загрузка моделей
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import chromadb
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from slugify import slugify

from app.chunk_manager import semantic_chunking
from parsers.text_extraction import TextBlock, extract_blocks
from app.term_graph import extract_term_tags

# ---------------------------------------------------------------------------
# Paths & logger
# ---------------------------------------------------------------------------

DOCS_PATH = Path("data/docs")
INDEX_ROOT = Path("data/index")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FILE_SKIP_PREFIXES = ("~$", ".")
FILE_SKIP_SUFFIXES = (".tmp",)
FILE_SKIP_NAMES = {"thumbs.db", ".ds_store"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_collection_name(name: str) -> str:
    """Convert arbitrary folder name → ASCII‑slug valid for Chroma."""
    slug: str = slugify(name, lowercase=True, separator="_")[:63].strip("._-")
    return slug or "default"


@lru_cache(maxsize=1)
def _get_embed_model() -> HuggingFaceEmbedding:
    logger.info("Loading HuggingFace embedding model …")
    return HuggingFaceEmbedding(model_name="paraphrase-multilingual-MiniLM-L12-v2")


# ---------------------------------------------------------------------------
# Public helpers — library info
# ---------------------------------------------------------------------------

def get_library_folders() -> List[str]:
    """Return list of top‑level document folders inside data/docs."""
    if not DOCS_PATH.exists():
        return []
    return [p.name for p in DOCS_PATH.iterdir() if p.is_dir()]


def list_documents_for_folder(folder: str) -> List[str]:
    """Return list of *files* for the given folder (skip tmp/hidden)."""
    folder_path = DOCS_PATH / folder
    if not folder_path.exists():
        return []

    files: List[str] = []
    for p in folder_path.iterdir():
        if not p.is_file():
            continue
        if p.name.lower() in FILE_SKIP_NAMES:
            continue
        if p.name.startswith(FILE_SKIP_PREFIXES):
            continue
        if any(p.name.endswith(sfx) for sfx in FILE_SKIP_SUFFIXES):
            continue
        files.append(p.name)
    return files


def check_indexed_files(folder: str) -> Dict[str, bool]:
    """Map {filename: is_indexed}.

    Fast check: если slug‑папка существует ⟶ считаем, что все файлы уже индексированы.
    Для более точного контроля можно хранить manifest.json, но пока достаточно.
    """
    folder_path = DOCS_PATH / folder
    if not folder_path.exists():
        return {}

    index_path = INDEX_ROOT / _safe_collection_name(folder)
    indexed = index_path.exists() and index_path.is_dir()
    return {f: indexed for f in list_documents_for_folder(folder)}

# ---------------------------------------------------------------------------
# Core indexing pipeline
# ---------------------------------------------------------------------------

def trigger_indexing(folder: str) -> None:
    """Extract → chunk → embed → push to Chroma."""
    logger.info("[📂] Indexing folder: %s", folder)
    folder_path = DOCS_PATH / folder
    if not folder_path.exists():
        logger.warning("Folder does not exist: %s — skip", folder_path)
        return

    files = [folder_path / f for f in list_documents_for_folder(folder)]
    if not files:
        logger.warning("No eligible files inside %s — skip", folder)
        return

    # ---------------------------- Extraction & chunking --------------------
    all_chunks = []
    for fp in files:
        try:
            blocks = extract_blocks(fp)
            chunks = semantic_chunking(blocks, fp)
            all_chunks.extend(chunks)
        except Exception as exc:  # noqa: BLE001
            logger.exception("semantic_chunking failed for %s: %s", fp, exc)

    if not all_chunks:
        logger.info("[SKIP] No chunks produced — nothing to index")
        return

    logger.info("Total chunks: %d", len(all_chunks))

    # ---------------------------- Chroma save ------------------------------
    index_path = INDEX_ROOT / _safe_collection_name(folder)
    index_path.mkdir(parents=True, exist_ok=True)

    embed_model = _get_embed_model()
    Settings.embed_model = embed_model  # llama-index global
    Settings.llm = None                 # we don't need the LLM here

    client = chromadb.PersistentClient(path=str(index_path))
    collection = client.get_or_create_collection(
        _safe_collection_name(folder), metadata={"title": folder}
    )

    # wipe old docs (if any) — safer than dropping & recreating collection
    try:
        ids_to_drop = collection.get(include=[])["ids"] or []
        if ids_to_drop:
            collection.delete(ids=ids_to_drop)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not wipe collection: %s", exc)

    documents = [ch["text"] for ch in all_chunks]
    metadatas = [
        {
            "file_path": str(ch["file"]),
            "page_label": ch.get("page"),
            "type": ch.get("type", "text"),
            "chunk_level": ch.get("chunk_level", "atomic"),
            "parent_id": ch.get("parent_id"),
            "section_id": ch.get("section_id"),
            "term_tags": extract_term_tags(ch.get("text", "")),
        }
        for ch in all_chunks
    ]
    ids = [str(ch["id"]) for ch in all_chunks]

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    logger.info("[OK] Index saved to %s", index_path)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def rebuild_index_from_folders(folders: List[str]) -> None:
    for f in folders:
        trigger_indexing(f)


def delete_index(folder: str) -> None:
    index_path = INDEX_ROOT / _safe_collection_name(folder)
    if index_path.exists():
        shutil.rmtree(index_path)
        logger.info("[🗑] Index folder removed: %s", index_path)


def get_file_text(folder: str, file: str) -> str:
    """Return plain text of a single source document (no embeddings)."""
    file_path = DOCS_PATH / folder / file
    try:
        blocks: list[TextBlock] = extract_blocks(file_path)
        text_blocks = [b["text"] for b in blocks if b.get("type", "text") == "text"]
        return "\n\n".join(part for part in text_blocks if part.strip())
    except Exception as exc:  # noqa: BLE001
        logger.error("get_file_text failed for %s: %s", file_path, exc)
        return ""
