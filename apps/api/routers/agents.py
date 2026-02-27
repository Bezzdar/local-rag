import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..services.agent_registry import list_agents as registry_list_agents
from ..services.agent_registry import resolve_agent as registry_resolve_agent

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents")
@router.get("/api/agents")
def get_agents() -> list[dict[str, Any]]:
    """Возвращает список агентов с устойчивым fallback-порядком."""
    return list_agents()


def list_agents() -> list[dict[str, Any]]:
    """Совместимый API для импортов из тестов/других модулей."""
    return registry_list_agents()


def resolve_agent(agent_id: str) -> dict[str, Any] | None:
    """Резолв агента через централизованный сервис."""
    return registry_resolve_agent(agent_id)
