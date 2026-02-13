"""search_engine.py — LLM‑driven семантический поиск по чанкам
-----------------------------------------------------------------
Поверхностная чистка (v0.1 / 2025‑06‑04)
  • Логирование + type hints
  • Робастный парсинг JSON из произвольного текста LLM
  • Pre‑normalize словари AND/OR/NOT
  • Никакая функциональность не сломана — API прежний
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Sequence, Tuple

from app.llm_generic import ask_llm
from app.user_settings import get_analytical_server_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 🔎 Вспомогательные функции
# ---------------------------------------------------------------------------
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_DEFAULT_QUERY: Dict[str, List[str]] = {"AND": [], "OR": [], "NOT": []}


def _extract_json(text: str) -> Dict[str, List[str]]:
    """Попытаться выудить JSON‑объект вида {"AND": [...], ...} из произвольного текста.

    Если распарсить не удаётся — возвращаем пустой словарь _DEFAULT_QUERY.
    """
    match = _JSON_RE.search(text)
    if not match:
        logger.debug("LLM returned no JSON: %s", text[:120])
        return _DEFAULT_QUERY.copy()

    try:
        raw = json.loads(match.group(0))
        # Гарантируем, что есть все ключи и значения‑списки строк
        parsed = {k.upper(): [str(w) for w in v] for k, v in raw.items() if k.upper() in _DEFAULT_QUERY}
        return {**_DEFAULT_QUERY, **parsed}
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("JSON parse failed: %s", exc, exc_info=False)
        return _DEFAULT_QUERY.copy()


# ---------------------------------------------------------------------------
# 🧠 LLM‑генерация поисковых запросов
# ---------------------------------------------------------------------------

def llm_generate_query(
    user_prompt: str,
    last_chunks: Sequence[dict] | None = None,
    prev_queries: Sequence[dict] | None = None,
) -> Tuple[Dict[str, List[str]], str]:
    """Сгенерировать поисковую формулу AND/OR/NOT с помощью LLM.

    Возвращает кортеж: (query_dict, raw_response).
    """
    context_fragments = " ".join(ch["text"][:100] for ch in last_chunks) if last_chunks else ""
    history = str(prev_queries) if prev_queries else ""

    prompt = (
        "На основе запроса пользователя сгенерируй поисковую формулу для поиска по библиотеке документов.\n"
        f"Запрос: {user_prompt}\n"
        + (f"Последние найденные фрагменты: {context_fragments}\n" if context_fragments else "")
        + (f"История уточнений: {history}\n" if history else "")
        + "Верни JSON с ключами AND, OR, NOT.\n"
        + "Пример:\n{\"AND\": [\"коррозия\", \"резервуар\"], \"NOT\": [\"очистка\"], \"OR\": [\"разрушение\", \"дефект\"]}"
    )

    raw = ask_llm(prompt, server_url=get_analytical_server_url())
    query = _extract_json(raw)
    return query, raw


# ---------------------------------------------------------------------------
# ⚡ Быстрый булев поиск по списку чанков
# ---------------------------------------------------------------------------

def run_fast_search(
    query: Dict[str, Sequence[str]],
    all_chunks: Sequence[dict],
    top_n: int = 30,
) -> List[dict]:
    """Прямолинейный поиск по AND/OR/NOT‑словам без эмбеддингов. O(N)."""

    # Пред‑нормализация запросных слов для speed‑up
    and_words = [w.lower() for w in query.get("AND", [])]
    or_words = [w.lower() for w in query.get("OR", [])]
    not_words = [w.lower() for w in query.get("NOT", [])]

    found: List[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "").lower()
        if (
            all(word in text for word in and_words)
            and not any(word in text for word in not_words)
            and (not or_words or any(word in text for word in or_words))
        ):
            found.append(chunk)
            if len(found) >= top_n:
                break  # 💨 ранний выход
    return found


# ---------------------------------------------------------------------------
# 📃 LLM‑суммаризация найденных чанков
# ---------------------------------------------------------------------------

def llm_summarize_chunks(chunks: Sequence[dict], user_prompt: str) -> str:
    """Попросить LLM выделить нужное из списка чанков."""
    if not chunks:
        return "Нет найденных релевантных фрагментов."

    # Ограничим контекст, чтобы не залить LLM огромным сообщением (>4k токенов)
    context_items = []
    tokens = 0
    for ch in chunks:
        snippet = ch["text"][:400]
        tokens += len(snippet) // 4  # ~грубая оценка 1 токен ≈ 4 символа
        if tokens > 3500:
            break
        context_items.append(f"- {snippet}")

    context = "\n\n".join(context_items)
    prompt = (
        "На основании только этих фрагментов:\n" f"{context}\n" f"Ответь на вопрос: {user_prompt}\n"
    )

    return ask_llm(prompt, server_url=get_analytical_server_url())
