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


def test_process_document_moves_file_and_writes_outputs(tmp_path, monkeypatch):
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
    assert source.exists() is False

    out_file = base_root / notebook_id / "chunks" / f"{doc_id}.json"
    registry = base_root / notebook_id / "registry.json"
    assert out_file.exists()
    assert registry.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data[0]["embedding_failed"] is False
    assert data[1]["embedding_failed"] is True
