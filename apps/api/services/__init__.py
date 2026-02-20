"""Пакетный модуль для 'apps/api/services'."""

# --- Imports ---
from .index_service import index_source
from .parse_service import extract_blocks
from .search_service import search

__all__ = ["index_source", "extract_blocks", "search"]
