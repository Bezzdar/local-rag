"""Системные промпты, шаблоны и сборка контекста для LLM-запросов."""
# --- Imports ---
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..schemas import ChatMessage


# --- Constants ---
DEFAULT_MODEL_HISTORY = 5

# RAG-режим: строгий, только на основе источников
_SYSTEM_RAG_WITH_SOURCES = (
    "Ты работаешь в строгом режиме RAG (Retrieval-Augmented Generation).\n"
    "Ниже предоставлены фрагменты из загруженной документации. "
    "Каждый фрагмент помечен номером источника в квадратных скобках, например [1], [2].\n\n"
    "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:\n"
    "1. Отвечай ИСКЛЮЧИТЕЛЬНО на основе предоставленных фрагментов.\n"
    "2. Каждое утверждение подкрепляй ссылкой: «Согласно [1], …» или «… как указано в [2]».\n"
    "3. Не используй собственные знания и не делай предположений вне контекста.\n"
    "4. Если в источниках есть противоречия — укажи это явно.\n"
    "5. Если информация частичная — укажи, что найдено, а чего нет в документации.\n"
    "6. Запрещены фразы: «возможно», «скорее всего», «я думаю», «по моему мнению».\n"
    "7. Формат ответа: [Ответ] → [Источник: документ, раздел, страница]\n\n"
    "ФРАГМЕНТЫ ДОКУМЕНТАЦИИ:\n\n{rag_context}"
)

# Model-режим: аналитический, источники найдены
_SYSTEM_MODEL_WITH_SOURCES = (
    "Ты работаешь в аналитическом режиме.\n"
    "Ниже предоставлены фрагменты из загруженной документации. "
    "Каждый фрагмент помечен номером источника в квадратных скобках, например [1], [2].\n\n"
    "ПРАВИЛА РАБОТЫ:\n"
    "1. Используй предоставленные источники как основу рассуждения.\n"
    "2. Ты можешь анализировать, делать выводы и предлагать решения, выходящие за рамки источников.\n"
    "3. Явно разделяй два типа контента в ответе:\n"
    "   • «[По документации]: …» — факты из источников с указанием [N]\n"
    "   • «[Анализ]: …» — твои выводы, рекомендации, рассуждения\n"
    "4. При ссылке на конкретный фрагмент используй его номер: «Согласно [1], …»\n"
    "5. Разрешены: «на мой взгляд», «рекомендую рассмотреть», «исходя из практики»\n\n"
    "ФРАГМЕНТЫ ДОКУМЕНТАЦИИ:\n\n{rag_context}"
)

# Model-режим: аналитический, источники не найдены
_SYSTEM_MODEL_NO_SOURCES = (
    "Ты работаешь в аналитическом режиме.\n"
    "Релевантной документации по данному запросу не найдено в загруженных источниках.\n\n"
    "ПРАВИЛА РАБОТЫ:\n"
    "1. Отвечай на основе своих профессиональных знаний.\n"
    "2. В начале ответа явно укажи, что ответ основан на общих знаниях, "
    "а не на загруженной документации.\n"
    "3. Используй маркировку «[Анализ / общие знания]: …» для всего ответа.\n"
    "4. Разрешены: «на мой взгляд», «рекомендую рассмотреть», «исходя из практики».\n"
    "5. Предположения разрешены при явном их обозначении."
)

_SYSTEM_AGENT_TEMPLATE = (
    "Ты специализированный доменный агент в составе мультиагентной системы.\n"
    "Работай строго в своей роли и давай практически применимые ответы.\n\n"
    "КАРТОЧКА АГЕНТА:\n{agent_context}\n\n"
    "ПРАВИЛА:\n"
    "1. Не выходи за пределы своей компетенции; если запрос вне зоны роли — явно сообщи об этом.\n"
    "2. Структурируй ответ: цель → действия → результат/чек-лист.\n"
    "3. Если в запросе есть неопределенность, предложи 2-3 уточняющих вопроса.\n"
    "4. Пиши конкретно, без воды."
)


# --- Functions ---
def build_chat_history(messages: Iterable[ChatMessage], limit: int = DEFAULT_MODEL_HISTORY) -> list[dict[str, str]]:
    """Обрезает историю диалога до окна контекста модели и убирает пустые реплики."""
    window = list(messages)[-limit:]
    return [{"role": item.role, "content": item.content} for item in window if item.content.strip()]


def build_rag_context(chunks: list[dict], source_order_map: dict[str, int] | None = None) -> str:
    """Формирует строку контекста из retrieved-чанков для вставки в prompt.

    Дополнительно стабилизирует нумерацию ссылок через source_order_map, чтобы
    индексы [N] в ответе модели совпадали с порядком документов в UI.

    Args:
        chunks: Retrieved chunks from search.
        source_order_map: Mapping source_id -> sequential document number (1-based).
                          When provided, [N] in LLM output = document number in notebook list.
    """
    if not chunks:
        return ""
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        src = Path(chunk.get("source", "")).name or "unknown"
        page = chunk.get("page")
        page_str = f" (стр. {page})" if isinstance(page, int) else ""
        text = (chunk.get("text") or "").strip()
        if text:
            source_id = chunk.get("source_id", "")
            if source_order_map and source_id in source_order_map:
                ref_num = source_order_map[source_id]
            else:
                ref_num = i
            parts.append(f"[{ref_num}] {src}{page_str}:\n{text}")
    return "\n\n".join(parts)


def build_messages_for_mode(
    chat_mode: str,
    history: list[dict[str, str]],
    rag_context: str = "",
    sources_found: bool = False,
) -> list[dict[str, str]]:
    """Собирает список сообщений для LLM с учётом режима и наличия источников.

    Args:
        chat_mode: "rag", "model" или "agent".
        history: История диалога (без системного сообщения).
        rag_context: Отформатированный контекст из retrieved чанков.
        sources_found: Были ли найдены релевантные источники.
    """
    if chat_mode == "rag":
        system_content = _SYSTEM_RAG_WITH_SOURCES.format(rag_context=rag_context)
    elif chat_mode == "agent":
        system_content = _SYSTEM_AGENT_TEMPLATE.format(
            agent_context=rag_context or "id=agent\nrole=generalist"
        )
    elif sources_found and rag_context:
        system_content = _SYSTEM_MODEL_WITH_SOURCES.format(rag_context=rag_context)
    else:
        system_content = _SYSTEM_MODEL_NO_SOURCES

    system_msg = {"role": "system", "content": system_content}
    return [system_msg] + history


def inject_rag_context(history: list[dict[str, str]], rag_context: str) -> list[dict[str, str]]:
    """Устаревший хелпер для совместимости: проксирует в build_messages_for_mode()."""
    return build_messages_for_mode("model", history, rag_context=rag_context, sources_found=bool(rag_context))
