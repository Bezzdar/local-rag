"""Lightweight terminology graph for industrial/technical document retrieval.

The graph is intentionally compact and dependency-free:
- nodes are normalized technical terms
- edges encode semantic relations (part_of, measured_by, causes, regulated_by, synonym)
- expansion is used for retrieval-time query broadening
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Set


# adjacency list with relation labels (future-ready for weighted logic)
TERM_GRAPH: dict[str, dict[str, str]] = {
    "коррозия": {
        "дефект": "is_a",
        "разрушение": "causes",
        "трубопровод": "affects",
        "резервуар": "affects",
        "скорость коррозии": "measured_by",
    },
    "дефект": {
        "трещина": "is_a",
        "разрушение": "is_a",
        "неразрушающий контроль": "detected_by",
    },
    "трубопровод": {
        "давление": "measured_by",
        "температура": "measured_by",
        "фланец": "part_of",
        "задвижка": "part_of",
    },
    "резервуар": {
        "давление": "measured_by",
        "температура": "measured_by",
        "стенка": "part_of",
    },
    "кипиа": {
        "датчик давления": "part_of",
        "датчик температуры": "part_of",
        "автоматика": "related_to",
    },
    "давление": {
        "предохранительный клапан": "regulated_by",
        "манометр": "measured_by",
    },
    "температура": {
        "термопара": "measured_by",
        "охлаждение": "regulated_by",
        "нагрев": "regulated_by",
    },
}


def norm_term(term: str) -> str:
    return term.strip().lower().replace("ё", "е")


def _neighbors(term: str) -> list[str]:
    t = norm_term(term)
    return list(TERM_GRAPH.get(t, {}).keys())


def expand_terms_with_graph(
    terms: Iterable[str],
    *,
    depth: int = 1,
    max_terms: int = 24,
) -> set[str]:
    """Expand seed terms with graph neighbors (BFS, bounded).

    depth=1 is usually enough for retrieval broadening.
    """
    seeds = [norm_term(t) for t in terms if norm_term(t)]
    if not seeds:
        return set()

    seen: Set[str] = set(seeds)
    q = deque((seed, 0) for seed in seeds)

    while q and len(seen) < max_terms:
        node, lvl = q.popleft()
        if lvl >= depth:
            continue
        for nb in _neighbors(node):
            if nb not in seen:
                seen.add(nb)
                if len(seen) >= max_terms:
                    break
                q.append((nb, lvl + 1))
    return seen


def extract_term_tags(text: str, *, limit: int = 16) -> List[str]:
    """Extract present graph terms from text for metadata tagging."""
    hay = norm_term(text)
    matched: list[str] = []
    for term in TERM_GRAPH:
        if term in hay:
            matched.append(term)
            if len(matched) >= limit:
                break
    return matched
