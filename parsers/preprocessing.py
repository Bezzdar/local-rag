"""preprocessing.py — sentence split + lemmatization с помощью Natasha
---------------------------------------------------------------------
Небольшой refactor (2025‑06‑04):
•  Lazy‑инициализация моделей Natasha (_get_models @lru_cache) ⇒ загружаются 1×
•  logging вместо print
•  Полные type hints
•  Пустой ввод возвращает [] без падения
Публичный API segment_and_lemmatize(text) НЕ менялся
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

from natasha import Doc, Segmenter, MorphVocab, NewsEmbedding, NewsMorphTagger
from razdel import sentenize

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_models() -> tuple[Segmenter, MorphVocab, NewsMorphTagger]:
    """Lazily create & cache heavy Natasha objects."""
    segmenter = Segmenter()
    morph_vocab = MorphVocab()
    emb = NewsEmbedding()
    morph_tagger = NewsMorphTagger(emb)
    return segmenter, morph_vocab, morph_tagger


def segment_and_lemmatize(text: str) -> List[str]:
    """Return a list of lemmatized sentences extracted from *text*.

    Empty or whitespace‑only input ⇒ returns empty list without errors.
    """
    if not text or not text.strip():
        logger.debug("segment_and_lemmatize(): input is empty — returning []")
        return []

    segmenter, morph_vocab, morph_tagger = _get_models()

    sentences = [s.text for s in sentenize(text)]
    result: List[str] = []

    for sent in sentences:
        doc = Doc(sent)
        doc.segment(segmenter)
        doc.tag_morph(morph_tagger)
        for token in doc.tokens:
            token.lemmatize(morph_vocab)
        result.append(" ".join(token.lemma for token in doc.tokens))

    return result
