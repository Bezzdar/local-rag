"""Тесты роутера агентов."""

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers import agents


def test_list_agents_delegates_to_registry_service(monkeypatch):
    monkeypatch.setattr(
        agents,
        "registry_list_agents",
        lambda: [{"id": "agent_alpha", "name": "Alpha", "description": "A", "version": "1.0.0", "requires": [], "tools": [], "notebook_modes": ["agent"], "provider": "ollama", "model": ""}],
    )

    result = agents.list_agents()

    assert [agent["id"] for agent in result] == ["agent_alpha"]


def test_agents_endpoint_available_on_both_paths():
    client = TestClient(app)

    response_api = client.get('/api/agents')
    response_plain = client.get('/agents')

    assert response_api.status_code == 200
    assert response_plain.status_code == 200
    assert isinstance(response_api.json(), list)
    assert isinstance(response_plain.json(), list)
