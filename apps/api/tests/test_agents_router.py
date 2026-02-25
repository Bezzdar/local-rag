"""Тесты загрузки агентных манифестов."""

from pathlib import Path

from apps.api.services import agent_registry


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

    monkeypatch.setattr(agent_registry, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agent_registry, "REGISTRY_PATH", registry)

    result = agent_registry.list_agents()

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

    monkeypatch.setattr(agent_registry, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agent_registry, "REGISTRY_PATH", agents_dir / "registry.json")

    result = agent_registry.list_agents()

    assert [agent["id"] for agent in result] == ["agent_legacy"]
    assert result[0]["notebook_modes"] == ["agent"]
    assert result[0]["requires"] == ["db"]


def test_resolve_agent_returns_first_when_id_missing(tmp_path: Path, monkeypatch):
    agents_dir = tmp_path / "agent"
    agents_dir.mkdir()

    registry = agents_dir / "registry.json"
    registry.write_text(
        '{"version":1,"agents":[{"id":"agent_alpha","name":"Alpha","description":"A","version":"1.0.0"}]}'
    )

    monkeypatch.setattr(agent_registry, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agent_registry, "REGISTRY_PATH", registry)

    resolved = agent_registry.resolve_agent("")

    assert resolved is not None
    assert resolved["id"] == "agent_alpha"
