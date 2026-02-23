"""Реэкспорт чанкеров и фабричная функция get_chunker()."""
# --- Imports ---
from __future__ import annotations

from ..models import ParserConfig
from .base import BaseChunker
from .context_enrichment import ContextEnrichmentChunker
from .general import GeneralChunker
from .hierarchy import HierarchyChunker
from .pcr import PCRChunker
from .symbol import SymbolChunker


# --- Functions ---
def get_chunker(config: ParserConfig) -> BaseChunker:
    """Фабрика чанкеров: возвращает стратегию разбивки по значению config.chunking_method."""
    mapping = {
        "general":             GeneralChunker,
        "context_enrichment":  ContextEnrichmentChunker,
        "hierarchy":           HierarchyChunker,
        "pcr":                 PCRChunker,
        "symbol":              SymbolChunker,
    }
    cls = mapping.get(config.chunking_method, GeneralChunker)
    return cls(config)


__all__ = [
    "BaseChunker",
    "GeneralChunker",
    "ContextEnrichmentChunker",
    "HierarchyChunker",
    "PCRChunker",
    "SymbolChunker",
    "get_chunker",
]
