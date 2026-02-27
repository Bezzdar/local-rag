"""Тесты сервиса реестра агентов."""

from pathlib import Path

from apps.api.services import agent_registry


def test_service_loads_agents_from_registry(tmp_path: Path, monkeypatch):
    agents_dir = tmp_path / "agent"
    agents_dir.mkdir()
    registry = agents_dir / "registry.json"
    registry.write_text(
        '{"version":2,"agents":[{"id":"chemist","name":"Chemist","description":"c","version":"1.0.0","provider":"ollama","model":"llama3.1:8b"}]}'
    )

    monkeypatch.setattr(agent_registry, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agent_registry, "REGISTRY_PATH", registry)

    result = agent_registry.list_agents()

    assert len(result) == 1
    assert result[0]["id"] == "chemist"
    assert result[0]["provider"] == "ollama"
