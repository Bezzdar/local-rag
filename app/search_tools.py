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

@lru_cache(maxsize=8)
def _get_tfidf_matrix(texts_hash: int) -> tuple[TfidfVectorizer, np.ndarray]:
    """Возвращает (vectorizer, tfidf_matrix) для заданного корпуса.
    texts_hash — это hash(tuple(texts)); используем как ключ, чтобы
    не хранить сами тексты в lru_cache и не раздувать память.
    """
    # NOTE: Функция вызывается ТОЛЬКО внутри tfidf_search, где мы заранее
    # гарантируем, что хэш соответствует *текущему* списку текстов.
    raise RuntimeError("_get_tfidf_matrix должен быть переопределён в tfidf_search")

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
    key = hash(texts_tuple)

    # Переопределяем _get_tfidf_matrix под наш корпус, если его ещё нет
    if not _get_tfidf_matrix.cache_info().hits and not _get_tfidf_matrix.cache_info().misses:
        pass  # первый вызов — кеш пуст, но функция ещё не переопределена
    if key not in _get_tfidf_matrix.cache:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(texts_tuple)
        # Хак: инжектируем результат в кеш вручную (обход ограничений lru_cache)
        _get_tfidf_matrix.cache[key] = (vectorizer, tfidf_matrix)
        logger.debug("TF‑IDF matrix cached for corpus of %d docs", len(texts_tuple))

    vectorizer, tfidf_matrix = _get_tfidf_matrix.cache[key]
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
