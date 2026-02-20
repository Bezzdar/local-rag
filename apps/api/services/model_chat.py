from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import httpx

from ..schemas import ChatMessage

MAX_HISTORY_MESSAGES = 20
DEFAULT_MODEL_HISTORY = 5
DEBUG_MODEL_MODE = os.getenv("DEBUG_MODEL_MODE", "0") == "1"

logger = logging.getLogger(__name__)


def _normalize_provider(provider: str) -> str:
    return (provider or "none").strip().lower()


def build_chat_history(messages: Iterable[ChatMessage], limit: int = DEFAULT_MODEL_HISTORY) -> list[dict[str, str]]:
    window = list(messages)[-limit:]
    return [{"role": item.role, "content": item.content} for item in window if item.content.strip()]


def _openai_headers(model: str) -> dict[str, str]:
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
    timeout_s: float = 60.0,
) -> str:
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

    payload = {
        "model": selected_model,
        "messages": history,
        "stream": False,
    }

    if DEBUG_MODEL_MODE:
        logger.info("generate_model_answer provider=%s endpoint=%s model=%s history=%s", selected_provider, endpoint, selected_model, history)

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
    timeout_s: float = 60.0,
):
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

    if selected_provider == "ollama":
        request_url = f"{endpoint}/api/chat"
        payload = {"model": selected_model, "messages": history, "stream": True}
        headers = None
    else:
        request_url = f"{endpoint}/v1/chat/completions"
        payload = {"model": selected_model, "messages": history, "stream": True}
        headers = _openai_headers(selected_model)

    if DEBUG_MODEL_MODE:
        logger.info("stream_model_answer provider=%s url=%s model=%s history=%s", selected_provider, request_url, selected_model, history)

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
