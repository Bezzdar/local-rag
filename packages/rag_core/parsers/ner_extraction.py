"""ner_extraction.py — минимальный модуль извлечения имён собственных (Natasha)
-----------------------------------------------------------------------------
Текущая задача — лёгкая шлифовка без изменения публичного API.  

Изменения (2025‑06‑04):
•   Lazy‑инициализация NamesExtractor через @lru_cache ⇒ загружается 1 × на процесс
•   Логирование исключений при отсутствии модели / пустой вход
•   Чёткие type hints + docstring
"""

# --- Imports ---
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

try:
    from natasha import NamesExtractor
except ImportError as exc:  # pragma: no cover
    # Natasha не установлена — сообщаем через лог и падаем позже при вызове
    NamesExtractor = None  # type: ignore[assignment]
    logger.warning("Natasha is not installed: `pip install natasha` — %s", exc)


# --- Основные блоки ---
@lru_cache(maxsize=1)
def _get_extractor() -> "NamesExtractor":  # type: ignore[name-defined]
    """Ленивая загрузка *NamesExtractor* (кэшируется в процессе)."""
    if NamesExtractor is None:  # pragma: no cover
        raise RuntimeError("Natasha is not available — install the package first")
    return NamesExtractor()


def extract_named_entities(text: str) -> List[Dict[str, Any]]:
    """Извлечь имена собственные из *text*.

    Возвращает список словарей (`fact.as_dict`). Пустой список, если сущностей нет.
    Исключение поднимается, если Natasha недоступна.
    """
    if not text:
        logger.debug("Received empty text for NER extraction")
        return []

    extractor = _get_extractor()
    matches = extractor(text)
    # Natasha >= 1.7: fact.as_dict; у старых версий — as_json()
    result = []
    for match in matches:
        fact = match.fact
        as_dict = getattr(fact, "as_dict", None)
        if callable(as_dict):
            result.append(as_dict())
        else:  # fall‑back — используем __dict__ без приватных полей
            result.append({k: v for k, v in fact.__dict__.items() if not k.startswith("_")})

    logger.debug("NER extracted %d entities", len(result))
    return result
