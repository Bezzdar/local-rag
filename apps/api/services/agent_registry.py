"""Сервис загрузки и резолва агентных манифестов."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_agents_dir() -> Path:
    """Определяет директорию `agent/` с приоритетом env/cwd/module-path."""
    env_value = os.getenv("AGENTS_DIR", "").strip()
    candidates: list[Path] = []
    if env_value:
        candidates.append(Path(env_value).expanduser())

    # На практике приложение обычно запускается из корня репозитория.
    candidates.append(Path.cwd() / "agent")

    module_path = Path(__file__).resolve()
    # Исторически в репозитории это parents[3] -> <repo>/agent.
    candidates.append(module_path.parents[3] / "agent")
    # Дополнительный fallback для нестандартных сборок/запусков.
    candidates.append(module_path.parents[2] / "agent")

    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except Exception:
            continue

    # Возвращаем первый кандидат для понятного логирования пути, даже если он не существует.
    return candidates[0] if candidates else Path("agent")


AGENTS_DIR = _resolve_agents_dir()
REGISTRY_PATH = AGENTS_DIR / "registry.json"


def normalize_agent_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Нормализует манифест агента к стабильной структуре для UI."""
    tools = raw.get("tools")
    requires = raw.get("requires")
    notebook_modes = raw.get("notebook_modes")
    provider = raw.get("provider")
    model = raw.get("model")

    return {
        "id": str(raw.get("id", "")).strip(),
        "name": str(raw.get("name", "")).strip(),
        "description": str(raw.get("description", "")).strip(),
        "version": str(raw.get("version", "0.0.0")).strip() or "0.0.0",
        "requires": [str(item).strip() for item in requires if str(item).strip()] if isinstance(requires, list) else [],
        "tools": [str(item).strip() for item in tools if str(item).strip()] if isinstance(tools, list) else [],
        "notebook_modes": [str(item).strip() for item in notebook_modes if str(item).strip()] if isinstance(notebook_modes, list) else ["agent"],
        "provider": str(provider or "ollama").strip().lower() or "ollama",
        "model": str(model or "").strip(),
    }


def load_agents_from_registry() -> list[dict[str, Any]]:
    """Загружает список агентов из registry.json."""
    if not REGISTRY_PATH.is_file():
        return []

    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse agent registry: %s", REGISTRY_PATH)
        return []

    raw_agents = payload.get("agents") if isinstance(payload, dict) else None
    if not isinstance(raw_agents, list):
        logger.warning("Invalid registry format (missing agents list): %s", REGISTRY_PATH)
        return []

    normalized = []
    for raw in raw_agents:
        if not isinstance(raw, dict):
            continue
        item = normalize_agent_manifest(raw)
        if item["id"] and item["name"]:
            normalized.append(item)

    return normalized


def discover_agents_from_folders() -> list[dict[str, Any]]:
    """Загружает список агентов из agent/*/manifest.json."""
    agents: list[dict[str, Any]] = []

    if not AGENTS_DIR.is_dir():
        logger.warning("Agents directory not found: %s", AGENTS_DIR)
        return agents

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        manifest_path = agent_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            normalized = normalize_agent_manifest(manifest)
            if normalized["id"] and normalized["name"]:
                agents.append(normalized)
        except Exception:
            logger.warning("Failed to read manifest for agent dir: %s", agent_dir.name)

    return agents


def list_agents() -> list[dict[str, Any]]:
    """Возвращает список агентов из registry.json или директории agent/."""
    agents = load_agents_from_registry()
    if agents:
        return agents
    return discover_agents_from_folders()


def resolve_agent(agent_id: str) -> dict[str, Any] | None:
    """Возвращает агента по id или первого доступного как fallback."""
    agents = list_agents()
    if not agents:
        return None

    normalized_id = (agent_id or "").strip()
    if normalized_id:
        for agent in agents:
            if agent.get("id") == normalized_id:
                return agent

    return agents[0]
