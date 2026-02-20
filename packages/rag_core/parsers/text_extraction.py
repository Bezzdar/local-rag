"""text_extraction.py — extraction + section-aware chunk-ready blocks."""

# --- Imports ---
from __future__ import annotations

import concurrent.futures as _fut
import hashlib
import logging
import os
import re
import unicodedata as _ud
from pathlib import Path
from statistics import fmean
from typing import Set, TypedDict

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# --- Основные блоки ---
class TextBlock(TypedDict):
    """Unified parser contract used across extraction/chunking/indexing."""

    text: str
    type: str
    page: int | str
    source: str
    section_id: str
    section_title: str


try:
    from simhash import Simhash  # type: ignore
except ModuleNotFoundError:  # pragma: no cover

    class Simhash:  # minimal fallback
        def __init__(self, text: str, bits: int = 64):
            self.value = int(hashlib.md5(text.encode()).hexdigest(), 16) & ((1 << bits) - 1)


try:
    from razdel import sentenize
except ModuleNotFoundError:  # pragma: no cover
    sentenize = None  # type: ignore[assignment]

try:
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.text_rank import TextRankSummarizer
except ModuleNotFoundError:  # pragma: no cover
    Tokenizer = None  # type: ignore[assignment]
    PlaintextParser = None  # type: ignore[assignment]
    TextRankSummarizer = None  # type: ignore[assignment]


try:
    from docx import Document  # type: ignore
    from docx.oxml.table import CT_Tbl  # type: ignore
    from docx.oxml.text.paragraph import CT_P  # type: ignore
    from docx.table import Table  # type: ignore
    from docx.text.paragraph import Paragraph  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    Document = None  # type: ignore


_NON_PRINTABLE = {"Cc", "Cf", "Cs", "Co", "Cn"}
_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,4}[.)]?\s+.+|[А-ЯA-Z][А-ЯA-Z0-9\s\-]{4,})$")


def _clean(text: str) -> str:
    cleaned = "".join(
        ch for ch in text if (_ud.category(ch) not in _NON_PRINTABLE or ch in "\n\t\r")
    )
    cleaned = re.sub(r"[ \t\f]+", " ", cleaned)
    cleaned = re.sub(r"[\r\n]+", "\n", cleaned)
    return cleaned.strip()


def _sentences(text: str) -> list[str]:
    if not text:
        return []
    if sentenize is None:
        return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    try:
        return [s.text.strip() for s in sentenize(text) if s.text.strip()]
    except Exception as exc:  # pragma: no cover
        logger.warning("razdel failed, regex fallback: %s", exc)
        return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _drop_repeated_page_noise(pages: list[str], *, min_ratio: float = 0.6) -> list[str]:
    if len(pages) < 3:
        return pages

    total = len(pages)
    line_hits: dict[str, int] = {}
    for page in pages:
        uniq = {ln.strip() for ln in page.splitlines() if 1 <= len(ln.strip()) <= 120}
        for ln in uniq:
            line_hits[ln] = line_hits.get(ln, 0) + 1

    repeated = {ln for ln, cnt in line_hits.items() if cnt / total >= min_ratio}
    if not repeated:
        return pages

    cleaned: list[str] = []
    for page in pages:
        kept = [ln for ln in page.splitlines() if ln.strip() not in repeated]
        cleaned.append(_clean("\n".join(kept)))
    logger.debug("Removed %d repeated lines", len(repeated))
    return cleaned


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return (title, text) sections; first section defaults to __root__."""
    lines = [ln.strip() for ln in text.splitlines()]
    sections: list[tuple[str, list[str]]] = [("__root__", [])]
    for ln in lines:
        if not ln:
            continue
        if _HEADING_RE.match(ln):
            sections.append((ln, []))
            continue
        sections[-1][1].append(ln)

    result: list[tuple[str, str]] = []
    for title, body_lines in sections:
        body = _clean("\n".join(body_lines))
        if body:
            result.append((title, body))
    return result or [("__root__", _clean(text))]


def _extract_pdf_pages(path: Path) -> list[str]:
    import fitz

    with fitz.open(path) as doc:
        pages: list[str] = [""] * doc.page_count
        with _fut.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as exe:
            futs = {exe.submit(lambda p: doc.load_page(p).get_text("text"), i): i for i in range(doc.page_count)}
            for fut in _fut.as_completed(futs):
                pages[futs[fut]] = _clean(fut.result())
    return _drop_repeated_page_noise(pages)


def _extract_txt(path: Path) -> str:
    return _clean(path.read_text(encoding="utf-8", errors="ignore"))


def _extract_docx(path: Path) -> str:
    if Document is None:
        raise ImportError("python-docx required: pip install python-docx")

    def iter_blocks(parent):
        elm = parent.element.body if hasattr(parent, "element") else parent._element  # type: ignore[attr-defined]
        for child in elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)  # type: ignore[arg-type]
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)  # type: ignore[arg-type]

    def table_to_md(tbl: Table) -> str:
        rows: list[str] = []
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
    parts: list[str] = []
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


def _adaptive_chunk_size(sentences: list[str], tokens_target: int = 512, *, min_sentences: int = 2, max_sentences: int = 16) -> int:
    token_lens = [max(1, len(re.findall(r"\w+", s, flags=re.UNICODE))) for s in sentences]
    avg = fmean(token_lens) if token_lens else 10.0
    estimated = max(1, int(tokens_target / avg))
    return max(min_sentences, min(max_sentences, estimated))


def _textrank_boundaries(text: str, ratio: float = 0.1, *, max_sentences: int = 250) -> list[int]:
    sents = _sentences(text)
    if len(sents) < 4 or len(sents) > max_sentences:
        return []
    if PlaintextParser is None or Tokenizer is None or TextRankSummarizer is None:
        return []
    parser = PlaintextParser.from_string(text, Tokenizer("russian"))
    summary = TextRankSummarizer()(parser.document, max(1, int(len(sents) * ratio)))
    return sorted({sents.index(str(s)) for s in summary if str(s) in sents})


def _is_duplicate(chunk: str, fingerprints: Set[int], threshold: int = 3) -> bool:
    fp = Simhash(chunk).value
    near = any(bin(fp ^ other).count("1") <= threshold for other in fingerprints)
    if not near:
        fingerprints.add(fp)
    return near


def extract_blocks(file_path: str | Path, *, use_textrank: bool = False) -> list[TextBlock]:
    """Extract normalized TextBlock list (unified contract)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    raw_blocks: list[TextBlock] = []
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = _extract_pdf_pages(path)
        for i, page in enumerate(pages, start=1):
            if not page:
                continue
            raw_blocks.append({"text": page, "type": "text", "page": i, "source": str(path)})
    elif suffix in {".docx", ".doc"}:
        txt = _extract_docx(path)
        raw_blocks.append({"text": txt, "type": "text", "page": 1, "source": str(path)})
    elif suffix in {".txt", ".log"}:
        txt = _extract_txt(path)
        raw_blocks.append({"text": txt, "type": "text", "page": 1, "source": str(path)})
    else:
        raise ValueError(f"Unsupported format: {suffix}")

    sectioned: list[TextBlock] = []
    for block in raw_blocks:
        section_pairs = _split_sections(block["text"])
        if use_textrank and len(section_pairs) == 1:
            bnd = _textrank_boundaries(section_pairs[0][1])
            if bnd:
                sents = _sentences(section_pairs[0][1])
                parts, start = [], 0
                for idx in bnd:
                    parts.append(" ".join(sents[start:idx]).strip())
                    start = idx
                parts.append(" ".join(sents[start:]).strip())
                section_pairs = [("__textrank__", p) for p in parts if p]

        for sec_idx, (title, sec_text) in enumerate(section_pairs, start=1):
            if not sec_text:
                continue
            out: TextBlock = {
                "text": sec_text,
                "type": block["type"],
                "page": block["page"],
                "source": block["source"],
                "section_id": f"p{block['page']}.s{sec_idx}",
                "section_title": title,
            }
            sectioned.append(out)

    logger.info("Extracted %d text blocks from %s", len(sectioned), path.name)
    return sectioned


def semantic_chunk(
    text: str,
    *,
    tokens_target: int = 512,
    textrank: bool = False,
    dedup: bool = True,
    overlap_sentences: int = 1,
    min_chunk_chars: int = 60,
) -> list[str]:
    sents = _sentences(text)
    if not sents:
        return []

    boundaries = set(_textrank_boundaries(text)) if textrank else set()
    per_chunk = _adaptive_chunk_size(sents, tokens_target)
    chunks: list[str] = []
    fp: Set[int] = set()
    buf: list[str] = []

    def emit(part: list[str]) -> None:
        chunk = " ".join(part).strip()
        if len(chunk) < min_chunk_chars:
            return
        if chunk and (not dedup or not _is_duplicate(chunk, fp)):
            chunks.append(chunk)

    for idx, sent in enumerate(sents):
        buf.append(sent)
        if len(buf) >= per_chunk or idx in boundaries:
            emit(buf)
            buf = buf[-overlap_sentences:] if overlap_sentences > 0 else []
    if buf:
        emit(buf)
    return chunks


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="Extract & chunk document text")
    ap.add_argument("file", help="Path to PDF/DOCX/TXT file")
    ap.add_argument("--textrank", action="store_true", help="Use TextRank segmentation")
    args = ap.parse_args()

    for i, block in enumerate(extract_blocks(args.file, use_textrank=args.textrank), 1):
        print(f"\n--- block {i} ({block.get('section_title', 'section')}) {'-'*20}\n{block['text'][:500]}…\n")
