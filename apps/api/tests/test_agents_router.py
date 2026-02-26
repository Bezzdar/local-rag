"""Тесты роутера агентов."""

from pathlib import Path

from apps.api.routers import agents


def test_list_agents_prefers_registry(tmp_path: Path, monkeypatch):
    agents_dir = tmp_path / "agent"
    agents_dir.mkdir()

    registry = agents_dir / "registry.json"
    registry.write_text(
        '{"version":1,"agents":[{"id":"agent_alpha","name":"Alpha","description":"A","version":"1.0.0","tools":["extract"],"requires":[],"notebook_modes":["agent"]}]}'
    )

    folder_agent = agents_dir / "agent_legacy"
    folder_agent.mkdir()
    (folder_agent / "manifest.json").write_text(
        '{"id":"agent_legacy","name":"Legacy","description":"legacy","version":"0.1.0"}'
    )

    monkeypatch.setattr(agents, "_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agents, "_REGISTRY_PATH", registry)

    result = agents.list_agents()

    assert [agent["id"] for agent in result] == ["agent_alpha"]
    assert result[0]["tools"] == ["extract"]


def test_list_agents_falls_back_to_folders(tmp_path: Path, monkeypatch):
    agents_dir = tmp_path / "agent"
    agents_dir.mkdir()

    folder_agent = agents_dir / "agent_legacy"
    folder_agent.mkdir()
    (folder_agent / "manifest.json").write_text(
        '{"id":"agent_legacy","name":"Legacy","description":"legacy","version":"0.1.0","requires":["db"]}'
    )

    monkeypatch.setattr(agents, "_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agents, "_REGISTRY_PATH", agents_dir / "registry.json")

    result = agents.list_agents()

    assert [agent["id"] for agent in result] == ["agent_legacy"]
    assert result[0]["notebook_modes"] == ["agent"]
    assert result[0]["requires"] == ["db"]


def test_agents_endpoint_available_on_both_paths():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)

    response_api = client.get('/api/agents')
    response_plain = client.get('/agents')

    assert response_api.status_code == 200
    assert response_plain.status_code == 200
    assert isinstance(response_api.json(), list)
    assert isinstance(response_plain.json(), list)
