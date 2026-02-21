"""Тесты сервиса эмбеддингов."""

# --- Imports ---
from __future__ import annotations

import json
from pathlib import Path

from apps.api.services.embedding_service import (
    EmbeddingConfig,
    EmbeddingEngine,
    EmbeddingProviderConfig,
    QuantizationConfig,
    suggest_quantization,
)


# --- Основные блоки ---
class DummyClient:
    def __init__(self, provider):
        self._embedding_dim = 4
        self.provider = provider

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if "fail" in text:
                vectors.append([0.0, 0.0, 0.0, 0.0])
            else:
                vectors.append([1.0, 2.0, 3.0, 4.0])
        return vectors


def test_suggest_quantization_modes():
    assert suggest_quantization(500, 128).method == "none"
    assert suggest_quantization(10_000, 128).method == "SQ"
    big = suggest_quantization(200_000, 130)
    assert big.method == "PQ"
    assert 130 % big.pq_m == 0


def test_process_document_keeps_file_by_default_and_writes_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr("apps.api.services.embedding_service.EmbeddingClient", DummyClient)

    parsing_root = tmp_path / "parsing"
    base_root = tmp_path / "base"
    notebook_id = "nb1"
    doc_id = "doc1"

    (parsing_root / notebook_id).mkdir(parents=True)
    source = parsing_root / notebook_id / f"{doc_id}.json"
    source.write_text(
        json.dumps(
            {
                "chunks": [
                    {"text": "hello world", "chunk_type": "text", "page_number": 1},
                    {"text": "fail item", "chunk_type": "text", "page_number": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    engine = EmbeddingEngine(
        EmbeddingConfig(
            provider=EmbeddingProviderConfig(base_url="http://localhost:11434", model_name="dummy"),
            batch_size=2,
            parsing_root=str(parsing_root),
            base_root=str(base_root),
            quantization=QuantizationConfig(method="none", enabled=False),
        )
    )

    embedded = engine.process_document(notebook_id, doc_id)
    assert len(embedded) == 2
    assert source.exists() is True

    out_file = base_root / notebook_id / "chunks" / f"{doc_id}.json"
    registry = base_root / notebook_id / "registry.json"
    assert out_file.exists()
    assert registry.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data[0]["embedding_failed"] is False
    assert data[1]["embedding_failed"] is True


def test_embed_document_from_parsing_returns_embedded_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr("apps.api.services.embedding_service.EmbeddingClient", DummyClient)

    parsing_root = tmp_path / "parsing"
    notebook_id = "nb1"
    doc_id = "doc2"
    (parsing_root / notebook_id).mkdir(parents=True)
    source = parsing_root / notebook_id / f"{doc_id}.json"
    source.write_text(json.dumps({"chunks": [{"text": "hello", "chunk_type": "text", "page_number": 1}]}), encoding="utf-8")

    engine = EmbeddingEngine(
        EmbeddingConfig(provider=EmbeddingProviderConfig(base_url="http://localhost:11434", model_name="dummy"), parsing_root=str(parsing_root))
    )
    embedded = engine.embed_document_from_parsing(notebook_id, doc_id)
    assert len(embedded) == 1
    assert source.exists() is True


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise RuntimeError(f"status={self.status_code}")

    def json(self) -> dict:
        return self._payload


class FakeHTTPClient:
    def __init__(self, *_args, **_kwargs):
        self.posts: list[str] = []

    def get(self, url: str) -> FakeResponse:
        if url.endswith('/api/tags'):
            return FakeResponse(200, {'models': []})
        return FakeResponse(404)

    def post(self, url: str, json: dict) -> FakeResponse:
        self.posts.append(url)
        if url.endswith('/api/embed'):
            return FakeResponse(404)
        if url.endswith('/api/embeddings') or url.endswith('/embed'):
            return FakeResponse(200, {'embeddings': [[1.0, 2.0, 3.0, 4.0] for _ in json['input']]})
        return FakeResponse(404)


def test_ollama_fallback_endpoint_on_404(monkeypatch):
    from apps.api.services import embedding_service

    monkeypatch.setattr(embedding_service.httpx, 'Client', FakeHTTPClient)
    client = embedding_service.EmbeddingClient(
        EmbeddingProviderConfig(base_url='http://localhost:11434', model_name='dummy', provider='ollama')
    )

    vectors = client.get_embeddings(['hello'])
    assert vectors[0] == [1.0, 2.0, 3.0, 4.0]
    assert any(url.endswith('/api/embed') for url in client._client.posts)
    assert any(url.endswith('/api/embeddings') for url in client._client.posts)


def test_base_url_api_suffix_is_not_duplicated(monkeypatch):
    from apps.api.services import embedding_service

    monkeypatch.setattr(embedding_service.httpx, 'Client', FakeHTTPClient)
    client = embedding_service.EmbeddingClient(
        EmbeddingProviderConfig(base_url='http://localhost:11434/api', model_name='dummy', provider='ollama')
    )

    client.get_embeddings(['hello'])
    assert all('/api/api/' not in url for url in client._client.posts)
