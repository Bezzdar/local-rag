"""Сервис генерации ответов на основе модели/шаблонов."""

# --- Imports ---
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

import httpx

from ..schemas import ChatMessage

MAX_HISTORY_MESSAGES = 20
DEFAULT_MODEL_HISTORY = 5
DEBUG_MODEL_MODE = os.getenv("DEBUG_MODEL_MODE", "0") == "1"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Системные промпты для каждого режима
# ---------------------------------------------------------------------------

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


# --- Основные блоки ---
def _normalize_provider(provider: str) -> str:
    """Нормализация названия провайдера к внутреннему формату (lowercase)."""
    return (provider or "none").strip().lower()


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
        chat_mode: "rag" или "model".
        history: История диалога (без системного сообщения).
        rag_context: Отформатированный контекст из retrieved чанков.
        sources_found: Были ли найдены релевантные источники.
    """
    if chat_mode == "rag":
        system_content = _SYSTEM_RAG_WITH_SOURCES.format(rag_context=rag_context)
    elif sources_found and rag_context:
        system_content = _SYSTEM_MODEL_WITH_SOURCES.format(rag_context=rag_context)
    else:
        system_content = _SYSTEM_MODEL_NO_SOURCES

    system_msg = {"role": "system", "content": system_content}
    return [system_msg] + history


def inject_rag_context(history: list[dict[str, str]], rag_context: str) -> list[dict[str, str]]:
    """Устаревший хелпер для совместимости: проксирует в build_messages_for_mode()."""
    return build_messages_for_mode("model", history, rag_context=rag_context, sources_found=bool(rag_context))


def _openai_headers(model: str) -> dict[str, str]:
    """Готовит auth-заголовки для OpenAI-compatible endpoint-а."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    logger.warning("OPENAI_API_KEY is not set; request will likely fail")
    return {}


async def generate_model_answer(
    *,
    provider: str,
    base_url: str,
    model: str,
    history: list[dict[str, str]],
    rag_context: str = "",
    chat_mode: str = "model",
    sources_found: bool = False,
    timeout_s: float = 60.0,
) -> str:
    """Нестриминговый запрос к LLM (single response)."""
    # Нормализуем runtime-параметры, чтобы дальше работать с единым форматом.
    selected_provider = _normalize_provider(provider)
    endpoint = (base_url or "").strip().rstrip("/")
    selected_model = (model or "").strip()

    if selected_provider == "none":
        return "Режим модели включен, но провайдер не настроен. Откройте Runtime Settings и выберите LLM-провайдера."

    if selected_provider != "ollama":
        return f"Неподдерживаемый провайдер: {provider}. Сейчас доступен только Ollama."

    if not endpoint:
        return "Не указан base_url для Ollama. Укажите адрес в Runtime Settings."

    if not selected_model:
        return "Не выбрана модель. Выберите модель в Runtime Settings."

    # Формируем итоговый список сообщений: system prompt + user/assistant history.
    messages = build_messages_for_mode(chat_mode, history, rag_context=rag_context, sources_found=sources_found)
    # Для нестриминга ожидаем единый ответ в JSON-структуре провайдера.
    payload = {
        "model": selected_model,
        "messages": messages,
        "stream": False,
    }

    if DEBUG_MODEL_MODE:
        logger.info("generate_model_answer provider=%s endpoint=%s model=%s rag_context_len=%s", selected_provider, endpoint, selected_model, len(rag_context))

    try:
        request_url = f"{endpoint}/api/chat" if selected_provider == "ollama" else f"{endpoint}/v1/chat/completions"
        headers = _openai_headers(selected_model) if selected_provider == "openai" else None
        logger.info(
            "Sending non-streaming request to LLM provider",
            extra={"event": "llm.request", "details": f"provider={selected_provider}; model={selected_model}; url={request_url}"},
        )
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(request_url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(
            "LLM non-streaming request failed",
            extra={"event": "llm.request.failed", "details": f"provider={selected_provider}; model={selected_model}; error={exc}"},
        )
        return f"Ошибка запроса к модели ({selected_model}): {exc}"

    # Разбираем оба популярных формата ответа: Ollama (message) и OpenAI (choices).
    data = response.json()
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

    return "Модель вернула пустой ответ."


async def stream_model_answer(
    *,
    provider: str,
    base_url: str,
    model: str,
    history: list[dict[str, str]],
    rag_context: str = "",
    chat_mode: str = "model",
    sources_found: bool = False,
    timeout_s: float = 60.0,
):
    """Стриминговый запрос к LLM c поддержкой Ollama/OpenAI-compatible SSE."""
    selected_provider = _normalize_provider(provider)
    endpoint = (base_url or "").strip().rstrip("/")
    selected_model = (model or "").strip()

    if selected_provider == "none":
        yield "Режим модели включен, но провайдер не настроен. Откройте Runtime Settings и выберите LLM-провайдера."
        return
    if selected_provider not in {"ollama", "openai"}:
        yield f"Неподдерживаемый провайдер: {provider}. Сейчас доступны Ollama и OpenAI-compatible."
        return
    if not endpoint:
        yield "Не указан base_url для LLM. Укажите адрес в Runtime Settings."
        return
    if not selected_model:
        yield "Не выбрана модель. Выберите модель в Runtime Settings."
        return

    messages = build_messages_for_mode(chat_mode, history, rag_context=rag_context, sources_found=sources_found)

    # Настраиваем endpoint/формат запроса под конкретный провайдер.
    if selected_provider == "ollama":
        request_url = f"{endpoint}/api/chat"
        payload = {"model": selected_model, "messages": messages, "stream": True}
        headers = None
    else:
        request_url = f"{endpoint}/v1/chat/completions"
        payload = {"model": selected_model, "messages": messages, "stream": True}
        headers = _openai_headers(selected_model)

    if DEBUG_MODEL_MODE:
        logger.info("stream_model_answer provider=%s url=%s model=%s rag_context_len=%s", selected_provider, request_url, selected_model, len(rag_context))

    received_packets = 0
    dropped_packets = 0
    received_chars = 0

    logger.info(
        "Opening streaming connection to LLM provider",
        extra={"event": "llm.stream.open", "details": f"provider={selected_provider}; model={selected_model}; url={request_url}"},
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream("POST", request_url, json=payload, headers=headers) as response:
                response.raise_for_status()
                # Получаем поток по строкам, фильтруем keep-alive и маркер завершения [DONE].
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        dropped_packets += 1
                        continue

                    # Парсим инкрементальные токены в формате выбранного провайдера.
                    if selected_provider == "ollama":
                        message = item.get("message")
                        if isinstance(message, dict):
                            token = message.get("content")
                            if isinstance(token, str) and token:
                                received_packets += 1
                                received_chars += len(token)
                                yield token
                    else:
                        choices = item.get("choices")
                        if isinstance(choices, list) and choices:
                            delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                            if isinstance(delta, dict):
                                token = delta.get("content")
                                if isinstance(token, str) and token:
                                    received_packets += 1
                                    received_chars += len(token)
                                    yield token
    except httpx.HTTPError as exc:
        logger.exception(
            "LLM streaming request failed",
            extra={
                "event": "llm.stream.failed",
                "details": f"provider={selected_provider}; model={selected_model}; received_packets={received_packets}; dropped_packets={dropped_packets}; error={exc}",
            },
        )
        raise RuntimeError(f"Ошибка запроса к модели ({selected_model}): {exc}") from exc

    logger.info(
        "LLM streaming finished",
        extra={
            "event": "llm.stream.completed",
            "details": f"provider={selected_provider}; model={selected_model}; received_packets={received_packets}; dropped_packets={dropped_packets}; received_chars={received_chars}",
        },
    )
