"""Пакетный модуль для `apps/api/services`."""

# --- Imports ---
from .index_service import index_source
from .parse_service import DocumentParser, ParserConfig
from .search_service import search

__all__ = ["index_source", "search", "DocumentParser", "ParserConfig"]
