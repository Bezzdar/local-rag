"""Реэкспорт экстракторов и фабричная функция get_extractor()."""
# --- Imports ---
from __future__ import annotations

from ..models import ParserConfig, UnsupportedFormatError
from .base import BaseExtractor
from .docx import DocxExtractor
from .ocr import OcrExtractor
from .pdf import PdfExtractor
from .text import TextExtractor


# --- Functions ---
def get_extractor(suffix: str, config: ParserConfig) -> BaseExtractor:
    """Фабрика экстракторов: возвращает стратегию извлечения текста по расширению файла."""
    mapping = {
        ".txt": TextExtractor,
        ".md":  TextExtractor,
        ".docx": DocxExtractor,
        ".pdf":  PdfExtractor,
    }
    cls = mapping.get(suffix)
    if cls is None:
        raise UnsupportedFormatError(f"Unsupported format: {suffix}")
    return cls(config)


__all__ = [
    "BaseExtractor",
    "TextExtractor",
    "DocxExtractor",
    "PdfExtractor",
    "OcrExtractor",
    "get_extractor",
]
