from __future__ import annotations

from typing import Iterable

import httpx

from ..schemas import ChatMessage

MAX_HISTORY_MESSAGES = 20


def _normalize_provider(provider: str) -> str:
    return (provider or "none").strip().lower()


def build_chat_history(messages: Iterable[ChatMessage], limit: int = MAX_HISTORY_MESSAGES) -> list[dict[str, str]]:
    window = list(messages)[-limit:]
    return [{"role": item.role, "content": item.content} for item in window if item.content.strip()]


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

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(f"{endpoint}/api/chat", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"Ошибка запроса к модели ({selected_model}): {exc}"

    data = response.json()
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

    return "Модель вернула пустой ответ."
