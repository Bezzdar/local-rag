"""Тесты health-check endpoint-ов."""

# --- Imports ---
from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


# --- Основные блоки ---
def test_root_endpoint_returns_service_links() -> None:
    response = client.get('/')
    assert response.status_code == 200
    payload = response.json()
    assert payload['name'] == 'Local RAG Assistant API'
    assert payload['docs'] == '/docs'
    assert payload['health'] == '/api/health'


def test_health_endpoints_return_ok() -> None:
    for endpoint in ('/health', '/api/health'):
        response = client.get(endpoint)
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
