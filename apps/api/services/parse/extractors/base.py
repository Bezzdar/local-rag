"""Базовый абстрактный класс для всех экстракторов форматов файлов."""
# --- Imports ---
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models import ParserConfig


# --- Models / Classes ---
class BaseExtractor(ABC):
    """Контракт для всех экстракторов форматов файлов."""

    def __init__(self, config: ParserConfig) -> None:
        self.config = config

    @abstractmethod
    def extract(self, path: Path) -> tuple[list[dict], Optional[int]]:
        """Возвращает (blocks, total_pages)."""
        ...
