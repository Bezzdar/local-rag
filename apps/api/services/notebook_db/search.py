"""FTS-запросы и векторный поиск по чанкам ноутбука."""
# --- Imports ---
from __future__ import annotations

import json
import math
import sqlite3
from typing import Any


# --- Functions ---
def _enabled_filter_clause(selected_source_ids: list[str] | None, only_enabled_tags: bool) -> tuple[str, list[Any]]:
    # Формируем WHERE-условие с учётом выбранных источников и тегов фильтрации
    where = ["d.is_enabled=1", "c.is_enabled=1"]
    params: list[Any] = []
    if selected_source_ids:
        placeholders = ",".join("?" for _ in selected_source_ids)
        where.append(f"d.doc_id IN ({placeholders})")
        params.extend(selected_source_ids)
    if only_enabled_tags:
        where.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM document_tags dt
                JOIN tags t ON t.tag=dt.tag
                WHERE dt.doc_id=d.doc_id AND t.is_enabled=0
            )
            """
        )
    return " AND ".join(where), params


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    top_k: int,
    selected_source_ids: list[str] | None = None,
    only_enabled_tags: bool = True,
) -> list[dict[str, Any]]:
    """Полнотекстовый поиск с fallback на LIKE и общий резервный список."""
    where_clause, params = _enabled_filter_clause(selected_source_ids, only_enabled_tags)
    rows = conn.execute(
        f"""
        SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
               d.filepath, d.filename, bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN chunks c ON c.rowid=chunks_fts.rowid
        JOIN documents d ON d.doc_id=c.doc_id
        WHERE chunks_fts MATCH ? AND {where_clause}
        ORDER BY score
        LIMIT ?
        """,
        [query, *params, top_k],
    ).fetchall()
    if rows:
        return [dict(row) for row in rows]

    terms = [term for term in query.strip().split() if term]
    if not terms:
        return []
    like_clauses = " OR ".join(["c.chunk_text LIKE ?" for _ in terms])
    like_values = [f"%{term}%" for term in terms]
    fallback_rows = conn.execute(
        f"""
        SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
               d.filepath, d.filename, 0.0 AS score
        FROM chunks c
        JOIN documents d ON d.doc_id=c.doc_id
        WHERE ({like_clauses}) AND {where_clause}
        LIMIT ?
        """,
        [*like_values, *params, top_k],
    ).fetchall()
    if fallback_rows:
        return [dict(row) for row in fallback_rows]

    generic_rows = conn.execute(
        f"""
        SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
               d.filepath, d.filename, 0.0 AS score
        FROM chunks c
        JOIN documents d ON d.doc_id=c.doc_id
        WHERE {where_clause}
        ORDER BY c.rowid DESC
        LIMIT ?
        """,
        [*params, top_k],
    ).fetchall()
    return [dict(row) for row in generic_rows]


def search_vector(
    conn: sqlite3.Connection,
    query_vector: list[float],
    top_k: int,
    selected_source_ids: list[str] | None = None,
    only_enabled_tags: bool = True,
) -> list[dict[str, Any]]:
    """Векторный поиск по cosine similarity поверх сохраненных embedding JSON."""
    where_clause, params = _enabled_filter_clause(selected_source_ids, only_enabled_tags)
    rows = conn.execute(
        f"""
        SELECT c.rowid, c.chunk_id, c.doc_id, c.chunk_text, c.page_number, c.section_header,
               d.filepath, d.filename, ce.embedding
        FROM chunk_embeddings ce
        JOIN chunks c ON c.rowid=ce.chunk_rowid
        JOIN documents d ON d.doc_id=c.doc_id
        WHERE {where_clause}
        """,
        params,
    ).fetchall()

    q_norm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
    scored: list[dict[str, Any]] = []
    for row in rows:
        vec = [float(x) for x in json.loads(row["embedding"])]
        vec_norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        score = float(sum(a * b for a, b in zip(vec, query_vector)) / (vec_norm * q_norm))
        item = dict(row)
        item["score"] = score
        scored.append(item)

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
