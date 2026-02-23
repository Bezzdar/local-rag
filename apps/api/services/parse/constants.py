"""Константы модуля парсинга: методы чанкинга, типы документов, паттерны иерархии."""
# --- Imports ---
from __future__ import annotations

import re


# --- Constants ---
# Supported chunking methods and document types
CHUNKING_METHODS = ["general", "context_enrichment", "hierarchy", "pcr", "symbol"]
DOC_TYPES = ["technical_manual", "gost", "api_docs", "markdown"]

# Patterns for different document types
_HIERARCHY_PATTERNS = {
    "gost": [
        (1, re.compile(r"^\d+\.\s+[А-ЯA-Z\w]")),
        (2, re.compile(r"^\d+\.\d+\.\s+")),
        (3, re.compile(r"^\d+\.\d+\.\d+\.\s+")),
    ],
    "technical_manual": [
        (1, re.compile(r"^(Глава|Chapter|РАЗДЕЛ|SECTION)\s+\d+", re.IGNORECASE)),
        (2, re.compile(r"^\d+\.\d+\s+[А-ЯA-Z\w]")),
        (3, re.compile(r"^\d+\.\d+\.\d+\s+")),
    ],
    "api_docs": [
        (1, re.compile(r"^#{1,2}\s+")),
        (2, re.compile(r"^#{3}\s+")),
        (3, re.compile(r"^#{4,}\s+")),
    ],
    "markdown": [
        (1, re.compile(r"^#\s+")),
        (2, re.compile(r"^##\s+")),
        (3, re.compile(r"^###\s+")),
        (4, re.compile(r"^#{4,}\s+")),
    ],
}
