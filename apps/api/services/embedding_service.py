"""Сервис вычисления/подготовки эмбеддингов."""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

import httpx

from ..config import CHUNKS_DIR, NOTEBOOKS_DB_DIR

try:
    import numpy as np
except Exception:  # noqa: BLE001
    np = None

logger = logging.getLogger(__name__)


class EmbeddingServerUnavailableError(RuntimeError):
    pass


class IndexCompatibilityError(RuntimeError):
    pass


@dataclass
class EmbeddingProviderConfig:
    base_url: str
    model_name: str
    provider: str = "ollama"
    endpoint: str | None = None
    enabled: bool = True
    fallback_dim: int = 384
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
    parsing_root: str = str(CHUNKS_DIR)
    base_root: str = str(NOTEBOOKS_DB_DIR)
    delete_parsing_after_embed: bool = False


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
        self._base_url = provider.base_url.rstrip("/")
        self._embedding_dim = max(1, int(provider.fallback_dim or 384))
        self._active_embed_target = self._embedding_targets()[0]
        self._model_candidates = self._build_model_candidates(provider.model_name)
        self._active_model = self._model_candidates[0]
        self._disabled_due_to_model_not_found = False
        self._available = False
        if not provider.enabled:
            return
        if self.health_check():
            probe = self.get_embeddings(["dimension probe"], use_retry=False)
            if probe and probe[0]:
                self._embedding_dim = len(probe[0])
                self._available = True

    def health_check(self) -> bool:
        try:
            response = self._client.get(f"{self._base_url}/api/tags")
            return response.status_code < 500
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _zero(self) -> list[float]:
        return [0.0 for _ in range(self._embedding_dim)]


    def _build_model_candidates(self, model_name: str) -> list[str]:
        raw = (model_name or '').strip()
        if not raw:
            return ['']
        candidates = [raw]
        base_name = raw.split(':', 1)[0].strip()
        if base_name and base_name not in candidates:
            candidates.append(base_name)
        return candidates

    def _model_exists_on_server(self, model_name: str) -> bool:
        try:
            response = self._client.get(f"{self._base_url}/api/tags")
            if response.status_code >= 500:
                return False
            data = response.json() if hasattr(response, 'json') else {}
            models = data.get('models', []) if isinstance(data, dict) else []
            names = [item.get('name', '').strip() for item in models if isinstance(item, dict) and item.get('name')]
            if not names:
                return True
            target = model_name.strip().lower()
            return any(name.lower() == target for name in names)
        except Exception:
            return True

    def _is_model_not_found_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return '404' in message or 'not found' in message or 'model' in message and 'status=404' in message

    def _embedding_targets(self) -> list[tuple[str, Literal["native", "openai", "legacy"]]]:
        if self._provider.endpoint:
            custom = self._provider.endpoint if self._provider.endpoint.startswith("/") else f"/{self._provider.endpoint}"
            return [(custom, "native")]
        if (self._provider.provider or "ollama").lower() == "openai":
            return [("/v1/embeddings", "openai")]
        if self._base_url.endswith("/api"):
            return [("/embed", "native"), ("/embeddings", "legacy"), ("/v1/embeddings", "openai")]
        else:
            return [('/api/embed', 'native'), ('/api/embeddings', 'legacy'), ('/v1/embeddings', 'openai')]

    def _parse_embeddings_response(self, response: httpx.Response, expected_size: int) -> list[list[float]]:
        data = response.json()
        if isinstance(data, dict):
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list):
                result = [item if isinstance(item, list) else self._zero() for item in embeddings]
                return (result + [self._zero()] * expected_size)[:expected_size]
            openai_items = data.get("data")
            if isinstance(openai_items, list):
                result = []
                for item in openai_items:
                    if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                        result.append(item["embedding"])
                    else:
                        result.append(self._zero())
                return (result + [self._zero()] * expected_size)[:expected_size]
            single = data.get("embedding")
            if isinstance(single, list):
                return [single]
        return [self._zero() for _ in range(expected_size)]

    def _request_embeddings(self, path: str, mode: Literal["native", "openai", "legacy"], texts: list[str]) -> list[list[float]]:
        url = f"{self._base_url}{path}"
        if mode == "legacy":
            vectors: list[list[float]] = []
            for text in texts:
                response = self._client.post(url, json={"model": self._active_model, "prompt": text})
                response.raise_for_status()
                vectors.extend(self._parse_embeddings_response(response, 1))
            return vectors
        payload = {"model": self._active_model, "input": texts}
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        return self._parse_embeddings_response(response, len(texts))

    def get_embeddings(self, texts: list[str], use_retry: bool = True) -> list[list[float]]:
        if not self._provider.enabled:
            return [self._zero() for _ in texts]
        if self._disabled_due_to_model_not_found:
            return [self._zero() for _ in texts]

        last_error: Exception | None = None
        model_candidates = [self._active_model] + [item for item in self._model_candidates if item != self._active_model]

        for model_name in model_candidates:
            if not model_name:
                continue
            if use_retry and not self._model_exists_on_server(model_name):
                continue

            self._active_model = model_name
            targets = [self._active_embed_target] + [item for item in self._embedding_targets() if item != self._active_embed_target]
            for candidate in targets:
                try:
                    embeddings = self._request_embeddings(candidate[0], candidate[1], texts)
                    self._active_embed_target = candidate
                    self._available = True
                    return [[float(x) for x in item] if isinstance(item, list) and item else self._zero() for item in embeddings]
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    continue

        if last_error and self._is_model_not_found_error(last_error):
            self._disabled_due_to_model_not_found = True
            logger.warning('Embedding model not found on Ollama server: %s', self._provider.model_name)

        self._available = False
        return [self._zero() for _ in texts]


class EmbeddingEngine:
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.client = EmbeddingClient(config.provider)
        self.config.embedding_dim = self.client.embedding_dim or self.config.embedding_dim
        self._indices: dict[str, object] = {}

    @property
    def is_embedding_available(self) -> bool:
        return self.client.is_available

    def process_document(self, notebook_id: str, doc_id: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> list[EmbeddedChunk]:
        parsing_file = Path(self.config.parsing_root) / notebook_id / f"{doc_id}.json"
        payload = json.loads(parsing_file.read_text(encoding="utf-8"))
        chunks = payload["chunks"] if isinstance(payload, dict) and "chunks" in payload else payload
        built = self.embed_chunks(chunks, notebook_id=notebook_id, doc_id=doc_id, progress_callback=progress_callback)
        self._add_vectors(notebook_id, [item.embedding for item in built if not item.embedding_failed])

        out_dir = Path(self.config.base_root) / notebook_id / "chunks"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{doc_id}.json").write_text(json.dumps([_embedded_to_dict(item) for item in built], ensure_ascii=False, indent=2), encoding="utf-8")
        self._update_registry(notebook_id, doc_id, len(built))
        if self.config.delete_parsing_after_embed:
            parsing_file.unlink(missing_ok=True)
        return built

    def embed_document_from_parsing(self, notebook_id: str, doc_id: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> list[EmbeddedChunk]:
        parsing_file = Path(self.config.parsing_root) / notebook_id / f"{doc_id}.json"
        payload = json.loads(parsing_file.read_text(encoding="utf-8"))
        chunks = payload["chunks"] if isinstance(payload, dict) and "chunks" in payload else payload
        return self.embed_chunks(chunks, notebook_id=notebook_id, doc_id=doc_id, progress_callback=progress_callback)

    def embed_chunks(self, chunks: list[dict], notebook_id: str, doc_id: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> list[EmbeddedChunk]:
        total, done = len(chunks), 0
        all_chunks: list[EmbeddedChunk] = []
        now = _now_iso()
        for start in range(0, total, self.config.batch_size):
            batch = chunks[start : start + self.config.batch_size]
            vectors = self.client.get_embeddings([item.get("embedding_text") or item.get("text", "") for item in batch])
            if self.config.normalize_embeddings:
                vectors = [_normalize(vec) for vec in vectors]
            for batch_index, (chunk, vector) in enumerate(zip(batch, vectors)):
                idx = start + batch_index
                chunk_id = chunk.get("chunk_id") or f"{doc_id}:{idx}"
                meta = ChunkMeta(chunk_id=chunk_id, doc_id=doc_id, notebook_id=notebook_id, chunk_index=idx, total_chunks=total, page_start=chunk.get("page_number"), page_end=chunk.get("page_number"), char_count=len(chunk.get("text", "")), token_count=max(1, len(chunk.get("text", "").split())) if chunk.get("text") else 0, language=None, content_type=_map_content_type(chunk), prev_chunk_id=f"{doc_id}:{idx - 1}" if idx > 0 else None, next_chunk_id=f"{doc_id}:{idx + 1}" if idx + 1 < total else None, heading_path=[v for v in [chunk.get("parent_header"), chunk.get("section_header")] if v], source_created_at=None, indexed_at=now)
                all_chunks.append(EmbeddedChunk(parsed_chunk=chunk, embedding=vector, embedding_model=self.config.provider.model_name, embedded_at=now, meta=meta, embedding_failed=not any(abs(x) > 0 for x in vector)))
                done += 1
            if progress_callback:
                progress_callback(done, total)
        return all_chunks

    def embed_query(self, query_text: str) -> list[float]:
        vector = self.client.get_embeddings([query_text])[0]
        return _normalize(vector) if self.config.normalize_embeddings else vector

    def _ensure_index(self, notebook_id: str) -> None:
        self._indices.setdefault(notebook_id, [] if np is None else np.zeros((0, self.config.embedding_dim), dtype="float32"))

    def _add_vectors(self, notebook_id: str, vectors: list[list[float]]) -> None:
        if not vectors:
            return
        self._ensure_index(notebook_id)
        if np is None:
            self._indices[notebook_id].extend(vectors)
            return
        arr = np.array(vectors, dtype="float32")
        self._indices[notebook_id] = np.vstack([self._indices[notebook_id], arr])

    def _update_registry(self, notebook_id: str, doc_id: str, chunk_count: int) -> None:
        path = Path(self.config.base_root) / notebook_id / "registry.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"documents": {}}
        payload.setdefault("documents", {})[doc_id] = {"doc_id": doc_id, "chunks": chunk_count, "indexed_at": _now_iso()}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
    if np is None:
        norm = math.sqrt(sum(x * x for x in vector))
        return vector if norm <= 0 else [float(x / norm) for x in vector]
    arr = np.array(vector, dtype="float32")
    norm = float(np.linalg.norm(arr))
    return vector if norm <= 0 else [float(x) for x in (arr / norm).astype("float32")]


def _map_content_type(chunk: dict) -> Literal["text", "heading", "list", "table", "code", "mixed"]:
    chunk_type = str(chunk.get("chunk_type") or chunk.get("type") or "text").lower()
    if chunk_type in {"header", "heading"}:
        return "heading"
    if chunk_type == "table":
        return "table"
    return "text"


def _embedded_to_dict(item: EmbeddedChunk) -> dict:
    return asdict(item)
