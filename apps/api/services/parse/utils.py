"""Утилиты модуля парсинга: токенизация, подсчёт токенов, обработка строк PDF."""
# --- Imports ---
from __future__ import annotations

import re
from typing import Optional

from .models import ChunkType

try:
    import tiktoken
except Exception:  # noqa: BLE001
    tiktoken = None


# --- Functions ---
def _tokenize(text: str) -> list[str]:
    """Простейшая токенизация по пробелам (fallback-режим)."""
    return text.split()


def _token_count(text: str) -> int:
    """Подсчет токенов через tiktoken, либо приближенная оценка длины."""
    if not text.strip():
        return 0
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:  # noqa: BLE001
            pass
    return max(1, int(len(_tokenize(text)) * 1.3))


def _sort_pdf_lines_multicolumn(lines: list[tuple[float, float, str, float]]) -> list[tuple[float, float, str, float]]:
    """Пытается восстановить порядок чтения для двухколоночного PDF."""
    if len(lines) < 3:
        return sorted(lines, key=lambda item: (item[0], item[1]))

    sorted_by_x = sorted(lines, key=lambda item: item[1])
    xs = [item[1] for item in sorted_by_x]
    gaps = [xs[idx + 1] - xs[idx] for idx in range(len(xs) - 1)]
    split_gap = max(gaps) if gaps else 0
    if split_gap < 80:
        return sorted(lines, key=lambda item: (item[0], item[1]))

    split_idx = gaps.index(split_gap) + 1
    split_x = (xs[split_idx - 1] + xs[split_idx]) / 2

    left = [line for line in lines if line[1] <= split_x]
    right = [line for line in lines if line[1] > split_x]
    left.sort(key=lambda item: item[0])
    right.sort(key=lambda item: item[0])
    return left + right


def _text_to_structured_blocks(text: str, page_number: int) -> list[dict]:
    """Нормализует plain text в блоки HEADER/TEXT для общего пайплайна."""
    blocks: list[dict] = []
    current_header: Optional[str] = None
    # Идем построчно: заголовки помечаем отдельно, чтобы не терять структуру документа.
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
        is_header = bool(re.match(r"^(#{1,6}\s+.+|\d+(?:\.\d+)*\s+.+)$", line))
        if is_header:
            current_header = re.sub(r"^#{1,6}\s*", "", line)
            blocks.append(
                {
                    "text": current_header,
                    "chunk_type": ChunkType.HEADER,
                    "page_number": page_number,
                    "section_header": current_header,
                    "parent_header": None,
                }
            )
            continue
        blocks.append(
            {
                "text": line,
                "chunk_type": ChunkType.TEXT,
                "page_number": page_number,
                "section_header": current_header,
                "parent_header": None,
            }
        )
    return blocks
