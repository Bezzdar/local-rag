"""Базовый абстрактный класс для всех методов чанкинга."""
# --- Imports ---
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ParsedChunk, ParserConfig


# --- Models / Classes ---
class BaseChunker(ABC):
    """Контракт для всех методов чанкинга."""

    def __init__(self, config: ParserConfig) -> None:
        self.config = config

    @abstractmethod
    def chunk(
        self,
        blocks: list[dict],
        doc_id: str,
        source_filename: str,
    ) -> list[ParsedChunk]:
        """Разбивает список блоков на чанки и возвращает их."""
        ...
