"""Роут для получения списка доступных агентов."""

from fastapi import APIRouter

from ..services.agent_registry import list_agents

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents")
def list_agents_route() -> list[dict]:
    """Возвращает список агентов из registry.json или директории agent/."""
    return list_agents()
