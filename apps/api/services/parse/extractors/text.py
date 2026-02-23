"""Экстрактор для текстовых файлов (.txt, .md)."""
# --- Imports ---
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..utils import _text_to_structured_blocks
from .base import BaseExtractor


# --- Models / Classes ---
class TextExtractor(BaseExtractor):
    """Извлекает содержимое .txt и .md файлов в структурированные блоки."""

    def extract(self, path: Path) -> tuple[list[dict], Optional[int]]:
        """Возвращает (blocks, total_pages)."""
        text = path.read_text(encoding="utf-8", errors="ignore")
        return _text_to_structured_blocks(text, page_number=1), 1
