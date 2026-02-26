"""Роут для получения списка доступных агентов."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..services.agent_registry import list_agents as registry_list_agents
from ..services.agent_registry import resolve_agent as registry_resolve_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])

_AGENTS_DIR = Path(__file__).resolve().parents[4] / "agent"
_REGISTRY_PATH = _AGENTS_DIR / "registry.json"


def _normalize_agent_manifest(raw: dict[str, Any]) -> dict[str, Any]:
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
        "notebook_modes": (
            [str(item).strip() for item in notebook_modes if str(item).strip()]
            if isinstance(notebook_modes, list)
            else ["agent"]
        ),
        "provider": str(provider or "ollama").strip().lower() or "ollama",
        "model": str(model or "").strip(),
    }


def _load_from_registry() -> list[dict[str, Any]]:
    if not _REGISTRY_PATH.is_file():
        return []

    try:
        payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse agent registry: %s", _REGISTRY_PATH)
        return []

    raw_agents = payload.get("agents") if isinstance(payload, dict) else None
    if not isinstance(raw_agents, list):
        logger.warning("Invalid registry format (missing agents list): %s", _REGISTRY_PATH)
        return []

    normalized: list[dict[str, Any]] = []
    for raw in raw_agents:
        if not isinstance(raw, dict):
            continue
        item = _normalize_agent_manifest(raw)
        if item["id"] and item["name"]:
            normalized.append(item)

    return normalized


def _discover_from_agent_folders() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []

    if not _AGENTS_DIR.is_dir():
        logger.warning("Agents directory not found: %s", _AGENTS_DIR)
        return agents

    for agent_dir in sorted(_AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        manifest_path = agent_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            normalized = _normalize_agent_manifest(manifest)
            if normalized["id"] and normalized["name"]:
                agents.append(normalized)
        except Exception:
            logger.warning("Failed to read manifest for agent dir: %s", agent_dir.name)

    return agents


@router.get("/agents")
def get_agents() -> list[dict[str, Any]]:
    """Возвращает список агентов из registry.json или директории agent/."""
    agents = _load_from_registry()
    if agents:
        return agents
    return _discover_from_agent_folders()


def list_agents() -> list[dict[str, Any]]:
    """Совместимый API для импортов из тестов/других модулей."""
    local_agents = _load_from_registry()
    if local_agents:
        return local_agents

    folder_agents = _discover_from_agent_folders()
    if folder_agents:
        return folder_agents

    return registry_list_agents()


def resolve_agent(agent_id: str) -> dict[str, Any] | None:
    """Резолв агента через централизованный сервис с fallback на локальный список."""
    resolved = registry_resolve_agent(agent_id)
    if resolved:
        return resolved

    agents = list_agents()
    if not agents:
        return None

    normalized_id = (agent_id or "").strip()
    if normalized_id:
        for agent in agents:
            if agent.get("id") == normalized_id:
                return agent

    return agents[0]
