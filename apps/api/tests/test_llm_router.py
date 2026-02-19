from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers import llm

client = TestClient(app)


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_list_models_returns_empty_for_none_provider() -> None:
    response = client.get('/api/llm/models', params={'provider': 'none'})
    assert response.status_code == 200
    assert response.json() == []


def test_list_models_fetches_ollama_models(monkeypatch) -> None:
    async def fake_get(self, url: str):
        assert url == 'http://localhost:11434/api/tags'
        return DummyResponse({'models': [{'name': 'llama3.1:8b'}, {'name': 'qwen2.5:7b'}]})

    monkeypatch.setattr(llm.httpx.AsyncClient, 'get', fake_get)

    response = client.get(
        '/api/llm/models',
        params={'provider': 'ollama', 'base_url': 'http://localhost:11434'},
    )
    assert response.status_code == 200
    assert response.json() == ['llama3.1:8b', 'qwen2.5:7b']
