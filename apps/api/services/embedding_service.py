"""Сервис вычисления/подготовки эмбеддингов."""

# --- Imports ---
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

import httpx

try:
    import numpy as np
except Exception as exc:  # pragma: no cover
    raise RuntimeError("numpy is required for embedding service") from exc

try:  # pragma: no cover - optional in tests
    import faiss
except Exception:  # noqa: BLE001
    faiss = None

logger = logging.getLogger(__name__)


# --- Основные блоки ---
class EmbeddingServerUnavailableError(RuntimeError):
    pass


class IndexCompatibilityError(RuntimeError):
    pass


@dataclass
class EmbeddingProviderConfig:
    base_url: str
    model_name: str
    api_timeout: int = 120


@dataclass
class QuantizationConfig:
    enabled: bool = True
    method: Literal["none", "SQ", "PQ"] = "SQ"
    sq_type: str = "QT_8bit"
    pq_m: int = 64
    pq_nbits: int = 8
    train_size: int = 10_000


@dataclass
class EmbeddingConfig:
    provider: EmbeddingProviderConfig
    embedding_dim: int = 0
    normalize_embeddings: bool = True
    batch_size: int = 16
    quantization: QuantizationConfig = field(default_factory=QuantizationConfig)
    parsing_root: str = "./parsing"
    base_root: str = "./base"


@dataclass
class ChunkMeta:
    chunk_id: str
    doc_id: str
    notebook_id: str
    chunk_index: int
    total_chunks: int
    page_start: int | None
    page_end: int | None
    char_count: int
    token_count: int
    language: str | None
    content_type: Literal["text", "heading", "list", "table", "code", "mixed"]
    prev_chunk_id: str | None
    next_chunk_id: str | None
    heading_path: list[str]
    source_created_at: str | None
    indexed_at: str


@dataclass
class EmbeddedChunk:
    parsed_chunk: dict
    embedding: list[float]
    embedding_model: str
    embedded_at: str
    meta: ChunkMeta
    embedding_failed: bool = False


@dataclass
class IndexMeta:
    notebook_id: str
    embedding_model: str
    embedding_dim: int
    quantization_method: str
    quantization_params: dict
    total_vectors: int
    created_at: str
    updated_at: str
    faiss_index_type: str


@dataclass
class SearchFilters:
    doc_ids: list[str] | None = None
    content_types: list[str] | None = None
    page_range: tuple[int, int] | None = None


@dataclass
class SearchResult:
    chunk: EmbeddedChunk
    score: float
    rank: int


@dataclass
class ProcessingReport:
    notebook_id: str
    started_at: str
    finished_at: str
    documents_found: int
    documents_processed: int
    documents_failed: int
    failed_docs: list[str]
    chunks_total: int
    chunks_embedded: int
    chunks_failed: int
    index_size_before: int
    index_size_after: int
    index_file_size_mb: float
    quantization_method: str
    embedding_model: str
    embedding_dim: int


class EmbeddingClient:
    def __init__(self, provider: EmbeddingProviderConfig):
        self._provider = provider
        self._client = httpx.Client(timeout=provider.api_timeout)
        if not self.health_check():
            raise EmbeddingServerUnavailableError(
                f"Embedding server unavailable: {provider.base_url}. Check Ollama availability."
            )
        probe = self.get_embeddings(["dimension probe"])
        self._embedding_dim = len(probe[0]) if probe and probe[0] else 0
        logger.info(
            "[embedding] Server: %s, model: %s, dim: %s",
            provider.base_url,
            provider.model_name,
            self._embedding_dim,
        )

    def health_check(self) -> bool:
        try:
            response = self._client.get(f"{self._provider.base_url}/api/tags")
            return response.status_code < 500
        except Exception:
            return False

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _zero(self) -> list[float]:
        return [0.0 for _ in range(self._embedding_dim)]

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._provider.model_name, "input": texts}
        for attempt in range(3):
            try:
                response = self._client.post(f"{self._provider.base_url}/api/embed", json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings") or []
                if len(embeddings) != len(texts):
                    embeddings = (embeddings + [self._zero()] * len(texts))[: len(texts)]
                result: list[list[float]] = []
                for index, item in enumerate(embeddings):
                    if not isinstance(item, list) or not item:
                        logger.warning("[embedding] Zero vector fallback for item %s", index)
                        result.append(self._zero())
                        continue
                    result.append([float(x) for x in item])
                return result
            except Exception as exc:
                if attempt == 2:
                    logger.warning("[embedding] Batch failed after retries: %s", exc)
                    return [self._zero() for _ in texts]
                time.sleep(2**attempt)
        return [self._zero() for _ in texts]


class EmbeddingEngine:
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.client = EmbeddingClient(config.provider)
        self.config.embedding_dim = self.client.embedding_dim
        self._indices: dict[str, object] = {}
        self._chunk_lookup: dict[str, dict[str, EmbeddedChunk]] = {}

    def process_notebook(
        self,
        notebook_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ProcessingReport:
        started_at = _now_iso()
        parsing_dir = Path(self.config.parsing_root) / notebook_id
        docs = sorted(parsing_dir.glob("*.json"))
        self._ensure_index(notebook_id)
        index_before = self._index_size(notebook_id)
        docs_processed = 0
        failed_docs: list[str] = []
        chunks_total = 0
        chunks_embedded = 0
        chunks_failed = 0

        for doc_path in docs:
            doc_id = doc_path.stem
            try:
                embedded = self.process_document(notebook_id, doc_id, progress_callback=progress_callback)
                docs_processed += 1
                chunks_total += len(embedded)
                chunks_embedded += sum(1 for item in embedded if not item.embedding_failed)
                chunks_failed += sum(1 for item in embedded if item.embedding_failed)
            except Exception:
                logger.exception("[embedding] Document failed: %s", doc_id)
                failed_docs.append(doc_id)

        self.save_index(notebook_id)
        index_after = self._index_size(notebook_id)
        index_file = Path(self.config.base_root) / notebook_id / "index.faiss"

        report = ProcessingReport(
            notebook_id=notebook_id,
            started_at=started_at,
            finished_at=_now_iso(),
            documents_found=len(docs),
            documents_processed=docs_processed,
            documents_failed=len(failed_docs),
            failed_docs=failed_docs,
            chunks_total=chunks_total,
            chunks_embedded=chunks_embedded,
            chunks_failed=chunks_failed,
            index_size_before=index_before,
            index_size_after=index_after,
            index_file_size_mb=(index_file.stat().st_size / (1024 * 1024)) if index_file.exists() else 0.0,
            quantization_method=self.config.quantization.method,
            embedding_model=self.config.provider.model_name,
            embedding_dim=self.config.embedding_dim,
        )
        return report

    def process_document(
        self,
        notebook_id: str,
        doc_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[EmbeddedChunk]:
        parsing_file = Path(self.config.parsing_root) / notebook_id / f"{doc_id}.json"
        payload = json.loads(parsing_file.read_text(encoding="utf-8"))
        chunks = payload["chunks"] if isinstance(payload, dict) and "chunks" in payload else payload
        built = self.embed_chunks(chunks, notebook_id=notebook_id, doc_id=doc_id, progress_callback=progress_callback)

        vectors = [item.embedding for item in built if not item.embedding_failed]
        self._add_vectors(notebook_id, vectors)

        base_dir = Path(self.config.base_root) / notebook_id
        chunks_dir = base_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        (chunks_dir / f"{doc_id}.json").write_text(
            json.dumps([_embedded_to_dict(item) for item in built], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._update_registry(notebook_id, doc_id, len(built))
        parsing_file.unlink(missing_ok=True)
        return built

    def embed_chunks(
        self,
        chunks: list[dict],
        notebook_id: str,
        doc_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[EmbeddedChunk]:
        total = len(chunks)
        done = 0
        all_chunks: list[EmbeddedChunk] = []
        now = _now_iso()

        for start in range(0, total, self.config.batch_size):
            batch = chunks[start : start + self.config.batch_size]
            texts = [item.get("text", "") for item in batch]
            vectors = self.client.get_embeddings(texts)
            if self.config.normalize_embeddings:
                vectors = [_normalize(vec) for vec in vectors]

            for batch_index, (chunk, vector) in enumerate(zip(batch, vectors)):
                idx = start + batch_index
                chunk_id = chunk.get("chunk_id") or f"{doc_id}:{idx}"
                is_failed = not any(abs(x) > 0 for x in vector)
                meta = ChunkMeta(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    notebook_id=notebook_id,
                    chunk_index=idx,
                    total_chunks=total,
                    page_start=chunk.get("page_number"),
                    page_end=chunk.get("page_number"),
                    char_count=len(chunk.get("text", "")),
                    token_count=max(1, len(chunk.get("text", "").split())) if chunk.get("text") else 0,
                    language=None,
                    content_type=_map_content_type(chunk),
                    prev_chunk_id=f"{doc_id}:{idx - 1}" if idx > 0 else None,
                    next_chunk_id=f"{doc_id}:{idx + 1}" if idx + 1 < total else None,
                    heading_path=[value for value in [chunk.get("parent_header"), chunk.get("section_header")] if value],
                    source_created_at=None,
                    indexed_at=now,
                )
                embedded = EmbeddedChunk(
                    parsed_chunk=chunk,
                    embedding=vector,
                    embedding_model=self.config.provider.model_name,
                    embedded_at=now,
                    meta=meta,
                    embedding_failed=is_failed,
                )
                all_chunks.append(embedded)
                done += 1
            if progress_callback:
                progress_callback(done, total)
        return all_chunks

    def embed_query(self, query_text: str) -> list[float]:
        vector = self.client.get_embeddings([query_text])[0]
        return _normalize(vector) if self.config.normalize_embeddings else vector

    def build_index(self, notebook_id: str) -> None:
        if faiss is None:
            self._indices[notebook_id] = np.zeros((0, self.config.embedding_dim), dtype="float32")
            return
        method = self.config.quantization.method if self.config.quantization.enabled else "none"
        dim = self.config.embedding_dim
        if method == "none":
            self._indices[notebook_id] = faiss.IndexFlatIP(dim)
            return
        if method == "SQ":
            sq_map = {
                "QT_8bit": "SQ8",
                "QT_4bit": "SQ4",
                "QT_fp16": "SQfp16",
            }
            self._indices[notebook_id] = faiss.index_factory(dim, sq_map.get(self.config.quantization.sq_type, "SQ8"), faiss.METRIC_INNER_PRODUCT)
            return
        m = min(self.config.quantization.pq_m, dim)
        m = _largest_divisor_le(dim, m)
        if m != self.config.quantization.pq_m:
            logger.warning("[embedding] pq_m corrected from %s to %s", self.config.quantization.pq_m, m)
            self.config.quantization.pq_m = m
        self._indices[notebook_id] = faiss.index_factory(dim, f"PQ{m}x{self.config.quantization.pq_nbits}", faiss.METRIC_INNER_PRODUCT)

    def save_index(self, notebook_id: str) -> None:
        base_dir = Path(self.config.base_root) / notebook_id
        base_dir.mkdir(parents=True, exist_ok=True)
        target = base_dir / "index.faiss"
        tmp = base_dir / "index.faiss.tmp"
        index = self._indices[notebook_id]
        if faiss is None:
            np.save(tmp, index)
            tmp_np = tmp.with_suffix(tmp.suffix + ".npy")
            os.replace(tmp_np, target)
        else:
            faiss.write_index(index, str(tmp))
            os.replace(tmp, target)

        meta_target = base_dir / "index.meta.json"
        meta_tmp = base_dir / "index.meta.json.tmp"
        created_at = _now_iso()
        meta = IndexMeta(
            notebook_id=notebook_id,
            embedding_model=self.config.provider.model_name,
            embedding_dim=self.config.embedding_dim,
            quantization_method=self.config.quantization.method,
            quantization_params=asdict(self.config.quantization),
            total_vectors=self._index_size(notebook_id),
            created_at=created_at,
            updated_at=created_at,
            faiss_index_type=self._faiss_type(notebook_id),
        )
        meta_tmp.write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(meta_tmp, meta_target)

    def load_index(self, notebook_id: str) -> None:
        base_dir = Path(self.config.base_root) / notebook_id
        meta_path = base_dir / "index.meta.json"
        index_path = base_dir / "index.faiss"
        if not meta_path.exists() or not index_path.exists():
            self.build_index(notebook_id)
            return

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("embedding_model") != self.config.provider.model_name:
            raise IndexCompatibilityError("Embedding model mismatch")
        if int(meta.get("embedding_dim", 0)) != self.config.embedding_dim:
            raise IndexCompatibilityError("Embedding dimension mismatch")

        if faiss is None:
            self._indices[notebook_id] = np.load(index_path)
        else:
            self._indices[notebook_id] = faiss.read_index(str(index_path))

    def reindex_notebook(self, notebook_id: str) -> None:
        chunks_dir = Path(self.config.base_root) / notebook_id / "chunks"
        docs = sorted(chunks_dir.glob("*.json"))
        self.build_index(notebook_id)
        for doc in docs:
            payload = json.loads(doc.read_text(encoding="utf-8"))
            original_chunks = [item.get("parsed_chunk", {}) for item in payload]
            embedded = self.embed_chunks(original_chunks, notebook_id=notebook_id, doc_id=doc.stem)
            vectors = [item.embedding for item in embedded if not item.embedding_failed]
            self._add_vectors(notebook_id, vectors)
            doc.write_text(json.dumps([_embedded_to_dict(item) for item in embedded], ensure_ascii=False, indent=2), encoding="utf-8")
        self.save_index(notebook_id)

    def search(
        self,
        notebook_id: str,
        query_vector: list[float],
        top_k: int = 10,
        filters: Optional[SearchFilters] = None,
    ) -> list[SearchResult]:
        self._ensure_index(notebook_id)
        oversample = 3 if filters else 1
        k = top_k * oversample
        if faiss is None:
            vectors = self._indices[notebook_id]
            if vectors.shape[0] == 0:
                return []
            q = np.array(query_vector, dtype="float32")
            scores = vectors @ q
            idxs = np.argsort(scores)[::-1][:k]
            pairs = [(float(scores[i]), int(i)) for i in idxs]
        else:
            scores, ids = self._indices[notebook_id].search(np.array([query_vector], dtype="float32"), k)
            pairs = [(float(s), int(i)) for s, i in zip(scores[0], ids[0]) if i >= 0]

        chunks = self._load_embedded_chunks(notebook_id)
        filtered: list[SearchResult] = []
        for score, i in pairs:
            if i >= len(chunks):
                continue
            chunk = chunks[i]
            if filters and not _matches_filters(chunk, filters):
                continue
            filtered.append(SearchResult(chunk=chunk, score=max(0.0, min(1.0, score)), rank=len(filtered) + 1))
            if len(filtered) >= top_k:
                break
        return filtered

    def _ensure_index(self, notebook_id: str) -> None:
        if notebook_id not in self._indices:
            self.load_index(notebook_id)

    def _add_vectors(self, notebook_id: str, vectors: list[list[float]]) -> None:
        if not vectors:
            return
        self._ensure_index(notebook_id)
        arr = np.array(vectors, dtype="float32")
        if faiss is None:
            self._indices[notebook_id] = np.vstack([self._indices[notebook_id], arr])
            return
        index = self._indices[notebook_id]
        if hasattr(index, "is_trained") and not index.is_trained:
            train_size = min(len(arr), self.config.quantization.train_size)
            if self.config.quantization.method == "PQ" and train_size < 256:
                logger.warning("[embedding] Not enough vectors for PQ training, fallback to SQ")
                self.config.quantization.method = "SQ"
                self.build_index(notebook_id)
                index = self._indices[notebook_id]
            if hasattr(index, "is_trained") and not index.is_trained:
                picks = arr[np.random.choice(len(arr), train_size, replace=False)]
                index.train(picks)
        index.add(arr)

    def _index_size(self, notebook_id: str) -> int:
        index = self._indices.get(notebook_id)
        if index is None:
            return 0
        if faiss is None:
            return int(index.shape[0])
        return int(index.ntotal)

    def _faiss_type(self, notebook_id: str) -> str:
        index = self._indices.get(notebook_id)
        if index is None:
            return "unknown"
        return type(index).__name__

    def _update_registry(self, notebook_id: str, doc_id: str, chunk_count: int) -> None:
        path = Path(self.config.base_root) / notebook_id / "registry.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"documents": {}}
        payload.setdefault("documents", {})[doc_id] = {
            "doc_id": doc_id,
            "chunks": chunk_count,
            "indexed_at": _now_iso(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_embedded_chunks(self, notebook_id: str) -> list[EmbeddedChunk]:
        chunks_dir = Path(self.config.base_root) / notebook_id / "chunks"
        result: list[EmbeddedChunk] = []
        for doc in sorted(chunks_dir.glob("*.json")):
            payload = json.loads(doc.read_text(encoding="utf-8"))
            for item in payload:
                meta = ChunkMeta(**item["meta"])
                result.append(
                    EmbeddedChunk(
                        parsed_chunk=item["parsed_chunk"],
                        embedding=item["embedding"],
                        embedding_model=item["embedding_model"],
                        embedded_at=item["embedded_at"],
                        meta=meta,
                        embedding_failed=item.get("embedding_failed", False),
                    )
                )
        return result


def suggest_quantization(n_vectors: int, embedding_dim: int) -> QuantizationConfig:
    if n_vectors < 1_000:
        return QuantizationConfig(method="none")
    if n_vectors < 100_000:
        return QuantizationConfig(method="SQ", sq_type="QT_8bit")
    return QuantizationConfig(method="PQ", pq_m=_largest_divisor_le(embedding_dim, 64), pq_nbits=8)


def _largest_divisor_le(value: int, limit: int) -> int:
    for candidate in range(min(value, limit), 0, -1):
        if value % candidate == 0:
            return candidate
    return 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(vector: list[float]) -> list[float]:
    arr = np.array(vector, dtype="float32")
    norm = float(np.linalg.norm(arr))
    if norm <= 0:
        return vector
    return [float(x) for x in (arr / norm).astype("float32")]


def _map_content_type(chunk: dict) -> Literal["text", "heading", "list", "table", "code", "mixed"]:
    chunk_type = str(chunk.get("chunk_type") or chunk.get("type") or "text").lower()
    if chunk_type in {"header", "heading"}:
        return "heading"
    if chunk_type in {"table"}:
        return "table"
    return "text"


def _matches_filters(chunk: EmbeddedChunk, filters: SearchFilters) -> bool:
    if filters.doc_ids and chunk.meta.doc_id not in filters.doc_ids:
        return False
    if filters.content_types and chunk.meta.content_type not in filters.content_types:
        return False
    if filters.page_range and chunk.meta.page_start is not None:
        low, high = filters.page_range
        if not (low <= chunk.meta.page_start <= high):
            return False
    return True


def _embedded_to_dict(item: EmbeddedChunk) -> dict:
    result = asdict(item)
    return result
