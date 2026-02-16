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
from app.term_graph import expand_terms_with_graph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 🔎 Вспомогательные функции
# ---------------------------------------------------------------------------
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_DEFAULT_QUERY: Dict[str, List[str]] = {"AND": [], "OR": [], "NOT": []}

# Базовая доменная карта синонимов/аббревиатур для техдоков (можно расширять).
_TERM_SYNONYMS: Dict[str, Sequence[str]] = {
    "кипиа": ("контрольно-измерительные приборы", "автоматика", "приборы"),
    "трубопровод": ("трубопроводы", "магистраль", "линия"),
    "коррозия": ("коррозионный", "ржавчина", "окисление"),
    "дефект": ("повреждение", "трещина", "разрушение"),
    "резервуар": ("емкость", "бак", "танк"),
    "давление": ("p", "избыточное давление"),
    "температура": ("t", "нагрев", "охлаждение"),
}


def _norm_term(term: str) -> str:
    return term.strip().lower().replace("ё", "е")


def _expand_term_variants(term: str) -> set[str]:
    normalized = _norm_term(term)
    if not normalized:
        return set()

    variants = {normalized}
    # forward map
    variants.update(_norm_term(v) for v in _TERM_SYNONYMS.get(normalized, ()))
    # reverse map
    for key, syns in _TERM_SYNONYMS.items():
        if normalized == _norm_term(key) or normalized in {_norm_term(v) for v in syns}:
            variants.add(_norm_term(key))
            variants.update(_norm_term(v) for v in syns)

    # graph expansion (Variant 3): related process/equipment/measurement terms
    variants.update(_norm_term(v) for v in expand_terms_with_graph(variants, depth=1, max_terms=20))
    return {v for v in variants if v}


def _expand_query_groups(words: Sequence[str]) -> list[set[str]]:
    groups: list[set[str]] = []
    for word in words:
        variants = _expand_term_variants(word)
        if variants:
            groups.append(variants)
    return groups


def _group_match(text: str, groups: Sequence[set[str]], mode: str) -> bool:
    if not groups:
        return True if mode == "all" else False

    checks = [any(variant in text for variant in variants) for variants in groups]
    return all(checks) if mode == "all" else any(checks)


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

    # Пред‑нормализация + расширение терминов синонимами/аббревиатурами
    and_groups = _expand_query_groups([str(w) for w in query.get("AND", [])])
    or_groups = _expand_query_groups([str(w) for w in query.get("OR", [])])
    not_groups = _expand_query_groups([str(w) for w in query.get("NOT", [])])

    ranked: list[tuple[int, dict]] = []
    for chunk in all_chunks:
        text = _norm_term(chunk.get("text", ""))

        and_ok = _group_match(text, and_groups, mode="all")
        not_ok = not _group_match(text, not_groups, mode="any") if not_groups else True
        or_ok = True if not or_groups else _group_match(text, or_groups, mode="any")

        if and_ok and not_ok and or_ok:
            score = 0
            score += sum(any(v in text for v in grp) for grp in and_groups) * 4
            score += sum(any(v in text for v in grp) for grp in or_groups) * 2
            # boost by sheer graph-term coverage inside chunk
            coverage = sum(text.count(v) for grp in and_groups + or_groups for v in grp)
            score += min(coverage, 20)
            ranked.append((score, chunk))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in ranked[:top_n]]


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
