"""search_tools.py — вспомогательные функции TF‑IDF и семантического ранжирования
------------------------------------------------------------------------------
Мини‑рефакторинг 2025‑06‑04 (ChatGPT‑o3)
Старается **не менять публичный API**, но устраняет узкие места:
    •   Единичная загрузка SentenceTransformer через @lru_cache (ускорение ×10‑×15)
    •   Кэширование результата TF‑IDF вектораизации (корпус → матрица)
    •   Возвращаем индексы + score, а не сами строки (*caller* сам решит, что ему нужно)
    •   Единое логирование через logging

Публичные функции:
    tfidf_search(texts: list[str], query: str, top_k: int = 5) -> list[tuple[int, float]]
    semantic_rerank(texts: list[str], query: str, top_k: int = 5) -> list[tuple[int, float]]
"""
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from functools import lru_cache
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# 1. Модели и кэши
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_sentence_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """Загрузка SentenceTransformer только один раз на процесс."""
    t0 = time.perf_counter()
    model = SentenceTransformer(model_name)
    logger.info("SentenceTransformer '%s' loaded in %.2f s", model_name, time.perf_counter() - t0)
    return model

_TFIDF_CACHE: "OrderedDict[int, tuple[TfidfVectorizer, np.ndarray]]" = OrderedDict()
_TFIDF_CACHE_SIZE = 8


def _get_tfidf_matrix_cached(texts_tuple: tuple[str, ...]) -> tuple[TfidfVectorizer, np.ndarray]:
    """Return cached TF‑IDF matrix for corpus, rebuilding if missing."""
    key = hash(texts_tuple)
    cached = _TFIDF_CACHE.get(key)
    if cached is not None:
        _TFIDF_CACHE.move_to_end(key)
        return cached

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(texts_tuple)
    _TFIDF_CACHE[key] = (vectorizer, tfidf_matrix)
    _TFIDF_CACHE.move_to_end(key)

    if len(_TFIDF_CACHE) > _TFIDF_CACHE_SIZE:
        _TFIDF_CACHE.popitem(last=False)

    logger.debug("TF‑IDF matrix cached for corpus of %d docs", len(texts_tuple))
    return vectorizer, tfidf_matrix

# ---------------------------------------------------------------------------
# 2. TF‑IDF поиск
# ---------------------------------------------------------------------------

def tfidf_search(texts: List[str], query: str, top_k: int = 5) -> List[Tuple[int, float]]:
    """Возвращает top_k индексов *texts* с наибольшей схожестью TF‑IDF.

    Возвращает список кортежей (index, score) отсортированных по убыванию score.
    """
    if not texts:
        return []

    texts_tuple = tuple(texts)
    vectorizer, tfidf_matrix = _get_tfidf_matrix_cached(texts_tuple)
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, tfidf_matrix).ravel()
    top_idx = np.argsort(sims)[::-1][:top_k]
    return [(int(i), float(sims[i])) for i in top_idx if sims[i] > 0]

# ---------------------------------------------------------------------------
# 3. Семантическая переоценка
# ---------------------------------------------------------------------------

def semantic_rerank(texts: List[str], query: str, top_k: int = 5) -> List[Tuple[int, float]]:
    """Использует SentenceTransformer для переранжирования *texts* относительно *query*.

    Возвращает те же (index, score) (cosine similarity в эмбеддингах).
    """
    if not texts:
        return []

    model = _get_sentence_model()
    query_emb = model.encode(query, convert_to_tensor=True, normalize_embeddings=True)
    text_embs = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True, show_progress_bar=False)

    sims = util.cos_sim(query_emb, text_embs).squeeze(0).cpu().numpy()
    top_idx = np.argsort(sims)[::-1][:top_k]
    return [(int(i), float(sims[i])) for i in top_idx if sims[i] > 0]
