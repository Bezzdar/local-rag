"""Роут для получения списка доступных агентов."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["agents"])
logger = logging.getLogger(__name__)

# Папка agents находится в корне репозитория (два уровня выше apps/api)
_AGENTS_DIR = Path(__file__).resolve().parents[4] / "agent"


@router.get("/agents")
def list_agents() -> list[dict]:
    """Возвращает список агентов, обнаруженных в директории agent/."""
    agents: list[dict] = []

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
            agents.append(manifest)
        except Exception:
            logger.warning("Failed to read manifest for agent dir: %s", agent_dir.name)

    return agents
