# chunk_manager.py — текстовый и семантический чанк‑менеджер
# ---------------------------------------------------------------------------
# Обновлён 2025‑06‑04 | ChatGPT‑o3 refactor
#   • Bug‑fix: tfidf_search ожидает список строк, не объектов
#   • ASCII‑slug имена коллекций Chroma (устраняет падения на кириллице)
#   • Pathlib + logging + lru_cache
#   • Единый центральный PersistentClient вместо множества
#   • Мелкий cleanup: type‑hints, докстринги, безопасные print → logging

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

import chromadb
# --- Chroma Collection type (API 0.4 vs 0.6) --------------------------------
try:
    from chromadb.api.models import Collection as Collection  # chromadb ≥ 0.5
except ImportError:  # старые версии
    try:
        from chromadb.api.types import Collection as Collection  # chromadb ≤ 0.4
    except ImportError:
        from typing import Any as Collection  # fallback-заглушка

# --- external deps
try:
    from slugify import slugify  # python‑slugify
except ImportError:  # fallback — грубый ASCII‑slug
    import unicodedata

    def slugify(value: str, separator: str = "_", lowercase: bool = True) -> str:  # type: ignore
        value = (
            unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        )
        value = re.sub(r"[^A-Za-z0-9._-]+", separator, value)
        value = value.lower() if lowercase else value
        return value.strip("._-")[:63]

from parsers.text_extraction import extract_blocks
from app.search_tools import tfidf_search
from app.config import DOCS_PATH

logger = logging.getLogger(__name__)

# ---------- Constants -------------------------------------------------------
ALLOWED_EXTS: tuple[str, ...] = (
    ".pdf",
    ".docx",
    ".txt",
    ".pptx",
    ".xlsx",
)
INDEX_ROOT = Path("data") / "index"
CHUNK_ROOT = Path("data") / "chunks"


# ---------- Chroma helpers --------------------------------------------------


def _safe_name(name: str) -> str:
    """Return a Chroma‑safe ASCII slug (3‑63 chars)."""
    return slugify(name, separator="_", lowercase=True)


@lru_cache(maxsize=128)
def _client_for_path(index_path: Path) -> chromadb.PersistentClient:  # type: ignore
    index_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(index_path))


def get_chroma_collection(folder: str) -> Collection:  # noqa: N802 – external API name
    """Return (and create if needed) Chroma collection for *folder*.

    Uses an ASCII slug for the actual collection name to avoid
    ``InvalidArgumentError`` on non‑Latin symbols, while keeping the original
    human name in metadata.
    """

    safe = _safe_name(folder)
    client = _client_for_path(INDEX_ROOT / safe)
    return client.get_or_create_collection(safe, metadata={"title": folder})


# ---------- ChunkStore ------------------------------------------------------


class ChunkStore:
    """In‑memory store of chunks for UI selection and editing."""

    def __init__(self) -> None:
        self.chunks: List[dict] = []  # [{id,text,file,page}]
        self.chunks_by_id: dict[str, dict] = {}

    # ――― basic ops ――― ---------------------------------------------------
    def clear(self) -> None:
        self.chunks.clear()
        self.chunks_by_id.clear()

    def set(self, chunk_list: list[dict]) -> None:
        self.chunks = chunk_list
        self.chunks_by_id = {ch["id"]: ch for ch in chunk_list}

    def remove_by_idx(self, idx: int | None) -> None:
        if idx is not None and 0 <= idx < len(self.chunks):
            del self.chunks[idx]
            self.chunks_by_id = {ch["id"]: ch for ch in self.chunks}

    # ――― add / remove by ids ――― -----------------------------------------
    def add_unique(self, add_chunks: Iterable[dict]) -> None:
        existing = set(self.chunks_by_id)
        for ch in add_chunks:
            if ch["id"] not in existing:
                self.chunks.append(ch)
                self.chunks_by_id[ch["id"]] = ch

    def remove_by_ids(self, remove_ids: set[str]) -> None:
        self.chunks = [ch for ch in self.chunks if ch["id"] not in remove_ids]
        for rid in remove_ids:
            self.chunks_by_id.pop(rid, None)

    def remove_one(self, id_: str) -> None:
        self.remove_by_ids({id_})

    # ――― ui helpers ――― ---------------------------------------------------
    def as_display(self) -> list[list[str]]:
        """Return rows [[preview,text‑link],…] for Streamlit ``st.table``."""
        rows = []
        for ch in self.chunks:
            ref = f"[{Path(ch['file']).name} стр.{ch['page']}](" \
                  f"file://{Path(ch['file']).resolve()}#page={ch['page']})"
            rows.append([
                ch["text"][:250].replace("\n", " "),
                ref,
            ])
        return rows

    # ――― search / filter ――― ---------------------------------------------
    def filter_by_query(self, query: str, mode: str = "and", top_k: int = 50) -> None:
        """Filter chunks using TF‑IDF search.

        * ``mode = 'and'`` – keep only matching chunks (intersection).
        * ``mode = 'not'`` – drop matching chunks from current set.
        """
        if not self.chunks:
            return

        texts = [ch["text"] for ch in self.chunks]
        try:
            idx_scores = tfidf_search(texts, query, top_k=top_k)  # returns List[tuple[int,float]]
        except Exception as exc:  # pragma: no cover – robust UI
            logger.error("TF‑IDF search failed: %s", exc)
            return

        indices = [idx for idx, _ in idx_scores]
        ids_matched = {self.chunks[i]["id"] for i in indices}

        if mode == "and":
            self.chunks = [self.chunks[i] for i in indices]
            self.chunks_by_id = {ch["id"]: ch for ch in self.chunks}
        elif mode == "not":
            self.remove_by_ids(ids_matched)


# ---------- helpers: filesystem & chunking ---------------------------------

def get_all_files_recursive(folder_path: Path, allowed_exts: tuple[str, ...] | None = None) -> list[Path]:
    """Recursively walk *folder_path* and return allowed file paths."""
    allowed_exts = allowed_exts or ALLOWED_EXTS
    files: list[Path] = []
    for root, _dirs, filenames in os.walk(folder_path):
        for fn in filenames:
            # skip system / temp
            if fn.lower() in {"thumbs.db", ".ds_store"} or fn.startswith("~$"):
                logger.debug("skip system/temp file: %s", fn)
                continue
            if fn.lower().endswith(allowed_exts):
                files.append(Path(root) / fn)
            else:
                logger.debug("skip unsupported ext: %s", fn)
    return files


def get_chunks_for_folder(folder: str) -> list[dict]:
    """Load & semantic‑chunk all documents in *folder* under DOCS_PATH."""
    folder_path = Path(DOCS_PATH) / folder
    chunks: list[dict] = []
    for file_path in get_all_files_recursive(folder_path):
        try:
            blocks = extract_blocks(str(file_path))
            chunks.extend(semantic_chunking(blocks, str(file_path)))
        except Exception as exc:  # pragma: no cover
            logger.exception("%s: block extraction failed: %s", file_path, exc)
    return chunks


# ---------- chroma: utils ---------------------------------------------------

def count_chunks_in_index(folder: str) -> int:
    """Return number of chunks in Chroma collection."""
    return get_chroma_collection(folder).count()


def get_chunk_by_number(folder: str, number: int) -> dict | None:
    """Return chunk \#number (1‑based) from collection."""
    coll = get_chroma_collection(folder)
    data = coll.get(include=["documents", "metadatas"])
    if 1 <= number <= len(data["documents"]):
        idx = number - 1
        meta = (data["metadatas"] or [{}])[idx]
        return {
            "text": data["documents"][idx],
            "file": meta.get("file_path", ""),
            "page": meta.get("page_label", "-"),
        }
    return None


# ---------- local storage (json) -------------------------------------------

CHUNK_ROOT.mkdir(parents=True, exist_ok=True)


def _chunk_file(folder: str) -> Path:
    return CHUNK_ROOT / f"{_safe_name(folder)}.json"


def save_chunks_for_folder(folder: str, chunks: list[dict]) -> None:
    """Persist chunks to JSON for offline analysis."""
    path = _chunk_file(folder)
    path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf‑8")


# --- Lazy ops: update / add / delete ---------------------------------------

def update_chunk_by_number(folder: str, number: int, chunk: dict, storage: str = "chroma") -> None:
    if storage == "chroma":
        coll = get_chroma_collection(folder)
        data = coll.get(include=["documents", "ids"])
        if 1 <= number <= len(data["documents"]):
            coll.update(ids=[data["ids"][number - 1]], documents=[chunk.get("text", "")])
    elif storage == "file":
        path = _chunk_file(folder)
        if not path.exists():
            raise FileNotFoundError("chunk file not found")
        chunks = json.loads(path.read_text("utf‑8"))
        if 1 <= number <= len(chunks):
            chunks[number - 1].update(chunk)
            save_chunks_for_folder(folder, chunks)


def add_chunk_to_folder(folder: str, chunk: dict, storage: str = "chroma") -> None:
    if storage == "chroma":
        import uuid

        coll = get_chroma_collection(folder)
        coll.add(
            documents=[chunk.get("text", "")],
            metadatas=[{k: v for k, v in chunk.items() if k != "text"}],
            ids=[str(uuid.uuid4())],
        )
    elif storage == "file":
        path = _chunk_file(folder)
        chunks = []
        if path.exists():
            chunks = json.loads(path.read_text("utf‑8"))
        chunks.append(chunk)
        save_chunks_for_folder(folder, chunks)


def delete_chunk_by_number(folder: str, number: int, storage: str = "chroma") -> None:
    if storage == "chroma":
        coll = get_chroma_collection(folder)
        data = coll.get(include=["ids", "documents"])
        if 1 <= number <= len(data["documents"]):
            coll.delete(ids=[data["ids"][number - 1]])
    elif storage == "file":
        path = _chunk_file(folder)
        if not path.exists():
            raise FileNotFoundError("chunk file not found")
        chunks = json.loads(path.read_text("utf‑8"))
        if 1 <= number <= len(chunks):
            chunks.pop(number - 1)
            save_chunks_for_folder(folder, chunks)


# ---------- semantic chunking ----------------------------------------------

def semantic_chunking(blocks: list, file_path: str) -> list[dict]:
    """Heuristic segmentation of *blocks* into semantic chunks."""

    chunks: list[dict] = []
    chunk_id = 0

    for raw in blocks:
        # ⇩⇩⇩ НОВОЕ: поддержка и dict-, и str-форматов блока
        if isinstance(raw, dict):
            text = raw.get("text", "").strip()
            b_type = raw.get("type", "text")
            page   = raw.get("page", "-")
        else:                       # старый формат - просто строка
            text  = str(raw).strip()
            b_type = "text"
            page   = "-"
        # ⇧⇧⇧-------------------------------------------------------------

        if not text:
            continue

        def add_chunk(txt: str) -> None:
            nonlocal chunk_id
            chunk_id += 1
            chunks.append(
                {
                    "id": f"{file_path}_{chunk_id}",
                    "text": txt,
                    "type": b_type,
                    "file": file_path,
                    "page": page,
                }
            )

        if b_type in {"table", "formula", "image", "header"}:  # 1‑to‑1
            add_chunk(text)
        elif b_type == "text":
            max_len = 1500
            if len(text) <= max_len:
                add_chunk(text)
            else:  # split by sentences, 4‑sentence window
                sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
                for i in range(0, len(sents), 4):
                    add_chunk(" ".join(sents[i : i + 4]))
        else:  # fallback – treat as atomic
            add_chunk(text)

    return chunks
