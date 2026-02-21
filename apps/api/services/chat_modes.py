"""Определение и обработка режимов чата."""

# --- Imports ---
from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Citation


# --- Основные блоки ---
@dataclass(frozen=True)
class ChatModeSpec:
    code: str
    title: str
    uses_retrieval: bool


CHAT_MODE_SPECS: tuple[ChatModeSpec, ...] = (
    ChatModeSpec(code="model", title="Модель", uses_retrieval=False),
    ChatModeSpec(code="agent", title="Агент", uses_retrieval=False),
    ChatModeSpec(code="rag", title="RAG", uses_retrieval=True),
)

CHAT_MODES_BY_CODE = {spec.code: spec for spec in CHAT_MODE_SPECS}
DEFAULT_CHAT_MODE = "rag"


def normalize_chat_mode(raw_mode: str) -> str:
    mode = (raw_mode or "").strip().lower()
    return mode if mode in CHAT_MODES_BY_CODE else DEFAULT_CHAT_MODE


def build_answer(mode: str, message: str, citations: list[Citation]) -> str:
    spec = CHAT_MODES_BY_CODE[mode]

    if mode == "agent":
        return "Агент: режим находится в разработке."

    if not spec.uses_retrieval:
        return f"{spec.title}: ответ на запрос '{message}' с учетом контекста переписки."

    if not citations:
        return f"{spec.title}: по запросу '{message}' релевантные фрагменты не найдены."

    first = citations[0]
    return (
        f"{spec.title}: найдено {len(citations)} фрагментов. "
        f"Основной источник: {first.filename} (p.{first.location.page}, {first.location.sheet})."
    )
