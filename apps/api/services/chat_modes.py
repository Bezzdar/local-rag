"""Определение и обработка режимов чата."""

# --- Imports ---
from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Citation


# --- Основные блоки ---
@dataclass(frozen=True)
class ChatModeSpec:
    """Описание режима чата для UI и маршрутизации backend-логики."""
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

# Пороги релевантности (применяются к нормализованным RRF-оценкам, диапазон 0–1)
SCORE_THRESHOLDS: dict[str, float] = {
    "rag": 0.75,    # строгий порог: только высокорелевантные чанки
    "model": 0.50,  # мягкий порог: чанки не менее 50 % от лучшего результата
}

# Сообщение при отсутствии релевантных источников в RAG-режиме (LLM не вызывается)
RAG_NO_SOURCES_MESSAGE = (
    "В загруженной документации релевантной информации не найдено. "
    "Уточните запрос или загрузите нужные документы."
)


def normalize_chat_mode(raw_mode: str) -> str:
    """Приводит входной режим к поддерживаемому значению или возвращает default."""
    mode = (raw_mode or "").strip().lower()
    return mode if mode in CHAT_MODES_BY_CODE else DEFAULT_CHAT_MODE


def build_answer(
    mode: str,
    message: str,
    citations: list[Citation],
    agent_id: str = "",
    agent_name: str = "",
    tools: list[str] | None = None,
) -> str:
    """Формирует ответ для режима Agent и fallback для остальных режимов."""
    if mode == "agent":
        resolved_name = (agent_name or "").strip()
        resolved_id = (agent_id or "").strip()
        label = f"{resolved_name} [{resolved_id}]" if resolved_name and resolved_id else (resolved_name or resolved_id or "Агент")
        tools_text = ", ".join(tools or []) if tools else "не указаны"
        return (
            f"Агент «{label}» активирован. "
            f"Доступные тулзы: {tools_text}. "
            f"Запрос принят: {message}"
        )

    # Fallback для непредвиденных случаев
    spec = CHAT_MODES_BY_CODE.get(mode)
    title = spec.title if spec else mode
    return f"{title}: ответ на запрос '{message}'."
