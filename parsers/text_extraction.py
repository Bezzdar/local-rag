"""
text_extraction.py – универсальный парсер + умная нарезка документов
===================================================================
Версия v1.0.0 | 2025-06-04 (stable)

Поддерживает:
    • PDF  – PyMuPDF (fitz)
    • DOCX/DOC – python-docx (таблицы → Markdown)
    • TXT/LOG – прямое чтение

Основные функции:
    extract_blocks(path)      → список «страниц»/блоков
    semantic_chunk(text, …)   → семантические чанки для эмбеддинга

Файл полностью перезаписан для устранения всех SyntaxError.
"""
from __future__ import annotations

import concurrent.futures as _fut
import hashlib
import logging
import os
import re
import unicodedata as _ud
from pathlib import Path
from typing import List, Set

import numpy as np

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# 0.  Simhash (с возможным fallback)
# ---------------------------------------------------------------------------
try:
    from simhash import Simhash  # type: ignore
except ModuleNotFoundError:  # pragma: no cover

    class Simhash:  # минимальная заглушка
        def __init__(self, text: str, bits: int = 64):
            self.value = int(hashlib.md5(text.encode()).hexdigest(), 16) & (
                (1 << bits) - 1
            )

# ---------------------------------------------------------------------------
# 1.  NLP библиотеки
# ---------------------------------------------------------------------------
from razdel import sentenize  # pip install razdel
from sumy.summarizers.text_rank import TextRankSummarizer  # pip install sumy
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer

# ---------------------------------------------------------------------------
# 2.  DOCX поддержка (опционально)
# ---------------------------------------------------------------------------
try:
    from docx import Document  # type: ignore
    from docx.table import Table  # type: ignore
    from docx.text.paragraph import Paragraph  # type: ignore
    from docx.oxml.table import CT_Tbl  # type: ignore
    from docx.oxml.text.paragraph import CT_P  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    Document = None  # type: ignore

# ---------------------------------------------------------------------------
# 3.  Служебные функции очистки
# ---------------------------------------------------------------------------
_NON_PRINTABLE = {"Cc", "Cf", "Cs", "Co", "Cn"}


def _clean(text: str) -> str:
    """Удаляет непечатные символы и нормализует пробелы."""
    cleaned = "".join(ch for ch in text if _ud.category(ch) not in _NON_PRINTABLE)
    cleaned = re.sub(r"[ \t\f]+", " ", cleaned)
    cleaned = re.sub(r"[\r\n]+", "\n", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# 4.  Предложение → список предложений
# ---------------------------------------------------------------------------

def _sentences(text: str) -> List[str]:
    if not text:
        return []
    try:
        return [s.text.strip() for s in sentenize(text) if s.text.strip()]
    except Exception as exc:  # pragma: no cover
        logger.warning("razdel failed – regex fallback (%s)", exc)
        return re.split(r"(?<=[.!?])\s+", text)


# ---------------------------------------------------------------------------
# 5.  Адаптивный размер чанка по tokens_target
# ---------------------------------------------------------------------------

def _adaptive_chunk_size(sentences: List[str], tokens_target: int = 512) -> int:
    """Estimate sentence-per-chunk without runtime downloads/dependencies."""
    token_lens = [max(1, len(re.findall(r"\w+", s, flags=re.UNICODE))) for s in sentences]
    avg = np.mean(token_lens) if token_lens else 10
    return max(1, int(tokens_target / avg))


# ---------------------------------------------------------------------------
# 6.  TextRank границы тем
# ---------------------------------------------------------------------------

def _textrank_boundaries(text: str, ratio: float = 0.1) -> List[int]:
    sents = _sentences(text)
    if len(sents) < 4:
        return []
    parser = PlaintextParser.from_string(text, Tokenizer("russian"))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, max(1, int(len(sents) * ratio)))
    return sorted({sents.index(str(s)) for s in summary if str(s) in sents})


# ---------------------------------------------------------------------------
# 7.  Дедупликация чанков
# ---------------------------------------------------------------------------

def _is_duplicate(chunk: str, fingerprints: Set[int], threshold: int = 3) -> bool:
    fp = Simhash(chunk).value
    near = any(bin(fp ^ other).count("1") <= threshold for other in fingerprints)
    if not near:
        fingerprints.add(fp)
    return near


# ---------------------------------------------------------------------------
# 8.  Извлечение PDF / TXT / DOCX
# ---------------------------------------------------------------------------

def _extract_pdf_pages(path: Path) -> List[str]:
    import fitz  # PyMuPDF

    with fitz.open(path) as doc:
        pages: list[str] = [""] * doc.page_count
        with _fut.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as exe:
            futs = {
                exe.submit(lambda p: doc.load_page(p).get_text("text"), i): i
                for i in range(doc.page_count)
            }
            for future in _fut.as_completed(futs):
                page_idx = futs[future]
                pages[page_idx] = _clean(future.result())
    return pages


def _extract_txt(path: Path) -> str:
    return _clean(path.read_text(encoding="utf-8", errors="ignore"))



def _extract_docx(path: Path) -> str:
    if Document is None:
        raise ImportError("python-docx required: pip install python-docx")

    def iter_blocks(parent):
        elm = parent.element.body if hasattr(parent, "element") else parent._element  # type: ignore
        for child in elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)  # type: ignore
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)  # type: ignore

    def table_to_md(tbl: Table) -> str:
        rows = []
        for row in tbl.rows:
            cells = [" " + cell.text.replace("|", " ").strip() + " " for cell in row.cells]
            rows.append("|".join(cells))
        if not rows:
            return ""
        header = rows[0]
        divider = "|".join([" --- " for _ in header.split("|")])
        body = "\n".join("|" + r + "|" for r in rows[1:])
        return f"|{header}|\n|{divider}|\n{body}"

    doc = Document(path)
    parts: List[str] = []
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            txt = block.text.strip()
            if txt:
                parts.append(txt)
        elif isinstance(block, Table):
            md = table_to_md(block)
            if md:
                parts.append(md)
    return _clean("\n\n".join(parts))


# ---------------------------------------------------------------------------
# 9.  Публичная точка – extract_blocks
# ---------------------------------------------------------------------------

def extract_blocks(file_path: str | Path, *, use_textrank: bool = False) -> List[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        blocks = _extract_pdf_pages(path)
    elif suffix in {".docx", ".doc"}:
        blocks = [_extract_docx(path)]
    elif suffix in {".txt", ".log"}:
        blocks = [_extract_txt(path)]
    else:
        raise ValueError(f"Unsupported format: {suffix}")

    if use_textrank and len(blocks) == 1:
        bnd = _textrank_boundaries(blocks[0])
        if bnd:
            sents = _sentences(blocks[0])
            chunks, start = [], 0
            for idx in bnd:
                chunks.append(" ".join(sents[start:idx]))
                start = idx
            chunks.append(" ".join(sents[start:]))
            blocks = chunks

    logger.info("Extracted %d blocks from %s", len(blocks), path.name)
    return blocks


# ---------------------------------------------------------------------------
# 10.  Семантическое нарезание
# ---------------------------------------------------------------------------

def semantic_chunk(
    text: str,
    *,
    tokens_target: int = 512,
    textrank: bool = False,
    dedup: bool = True,
) -> List[str]:
    sents = _sentences(text)
    if not sents:
        return []

    boundaries = set(_textrank_boundaries(text)) if textrank else set()
    per_chunk = _adaptive_chunk_size(sents, tokens_target)
    chunks: List[str] = []
    fp: Set[int] = set()
    buf: List[str] = []

    for idx, sent in enumerate(sents):
        buf.append(sent)
        done = len(buf) >= per_chunk or idx in boundaries
        if done:
            chunk = " ".join(buf).strip()
            if chunk and (not dedup or not _is_duplicate(chunk, fp)):
                chunks.append(chunk)
            buf = []
    if buf:
        chunk = " ".join(buf).strip()
        if chunk and (not dedup or not _is_duplicate(chunk, fp)):
            chunks.append(chunk)
    logger.info("Semantic chunking → %d chunks", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# 11.  CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="Extract & chunk document text")
    ap.add_argument("file", help="Path to PDF/DOCX/TXT file")
    ap.add_argument("--textrank", action="store_true", help="Use TextRank segmentation")
    args = ap.parse_args()

    for i, block in enumerate(extract_blocks(args.file, use_textrank=args.textrank), 1):
        print(f"\n--- block {i} {'-'*40}\n{block[:500]}…\n")
