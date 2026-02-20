"""Роуты приёма клиентских событий."""

# --- Imports ---
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["logs"])
logger = logging.getLogger(__name__)


# --- Основные блоки ---
class ClientEventPayload(BaseModel):
    event: str = Field(min_length=1, max_length=120)
    source: str = Field(default="web", max_length=40)
    notebook_id: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/client-events", status_code=202)
def log_client_event(payload: ClientEventPayload) -> dict[str, str]:
    safe_metadata = {k: str(v)[:500] for k, v in payload.metadata.items()}
    logger.info(
        "Client event captured",
        extra={
            "event": f"client.{payload.event}",
            "details": f"source={payload.source}; notebook_id={payload.notebook_id}; metadata={safe_metadata}",
        },
    )
    return {"status": "accepted"}
