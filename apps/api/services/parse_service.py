"""Сервис парсинга и нормализации документов."""

# --- Imports ---
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from langdetect import detect

from ..config import CHUNKS_DIR

try:
    import tiktoken
except Exception:  # noqa: BLE001
    tiktoken = None


# --- Основные блоки ---
class UnsupportedFormatError(Exception):
    pass


class ParseError(Exception):
    pass


class ChunkType(Enum):
    TEXT = "text"
    TABLE = "table"
    FORMULA = "formula"
    HEADER = "header"
    CAPTION = "caption"


@dataclass
class ParserConfig:
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50
    ocr_enabled: bool = True
    ocr_language: str = "rus+eng"


@dataclass
class ParsedChunk:
    text: str
    chunk_type: ChunkType
    chunk_index: int
    page_number: Optional[int]
    section_header: Optional[str]
    parent_header: Optional[str]
    prev_chunk_tail: Optional[str]
    next_chunk_head: Optional[str]
    doc_id: str
    source_filename: str


@dataclass
class DocumentMetadata:
    doc_id: str
    notebook_id: str
    filename: str
    filepath: str
    file_hash: str
    file_size_bytes: int
    title: Optional[str]
    authors: Optional[list[str]]
    year: Optional[int]
    source: Optional[str]
    total_pages: Optional[int]
    total_chunks: int
    language: str
    parser_version: str
    parsed_at: str
    tags: list[str] = field(default_factory=list)
    user_notes: Optional[str] = None
    is_enabled: bool = True
    individual_config: dict[str, int | bool | str | None] = field(
        default_factory=lambda: {
            "chunk_size": None,
            "chunk_overlap": None,
            "ocr_enabled": None,
            "ocr_language": None,
        }
    )


def _tokenize(text: str) -> list[str]:
    return text.split()


def _token_count(text: str) -> int:
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


class DocumentParser:
    def __init__(self, config: ParserConfig):
        self.config = config

    def parse(
        self,
        filepath: str,
        notebook_id: str,
        metadata_override: Optional[dict] = None,
    ) -> tuple[DocumentMetadata, list[ParsedChunk]]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(path)

        metadata_override = metadata_override or {}
        suffix = path.suffix.lower()
        blocks, total_pages = self._extract_blocks(path, suffix)

        doc_id = str(metadata_override.get("doc_id") or uuid4())
        chunks = self._chunk_blocks(blocks, doc_id=doc_id, source_filename=path.name)

        metadata = DocumentMetadata(
            doc_id=doc_id,
            notebook_id=notebook_id,
            filename=path.name,
            filepath=str(path),
            file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
            file_size_bytes=path.stat().st_size,
            title=metadata_override.get("title"),
            authors=metadata_override.get("authors"),
            year=metadata_override.get("year"),
            source=metadata_override.get("source"),
            total_pages=total_pages,
            total_chunks=len(chunks),
            language=self.detect_language("\n".join(block["text"] for block in blocks)[:1000]),
            parser_version="1.0.0",
            parsed_at=datetime.now(timezone.utc).isoformat(),
            individual_config=metadata_override.get("individual_config")
            or {
                "chunk_size": None,
                "chunk_overlap": None,
                "ocr_enabled": None,
                "ocr_language": None,
            },
            is_enabled=bool(metadata_override.get("is_enabled", True)),
        )
        self.save_parsing_result(notebook_id, metadata, chunks)
        return metadata, chunks

    def _extract_blocks(self, path: Path, suffix: str) -> tuple[list[dict], Optional[int]]:
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return self._text_to_structured_blocks(text, page_number=1), 1
        if suffix == ".docx":
            return self._extract_docx(path)
        if suffix == ".pdf":
            return self._extract_pdf(path)
        if suffix == ".xlsx":
            return ([{
                "text": f"Table content placeholder for {path.name}",
                "chunk_type": ChunkType.TABLE,
                "page_number": 1,
                "section_header": None,
                "parent_header": None,
            }], 1)
        if suffix in {".html", ".epub"}:
            raise UnsupportedFormatError(f"Format planned but not implemented yet: {suffix}")
        raise UnsupportedFormatError(f"Unsupported format: {suffix}")

    def _text_to_structured_blocks(self, text: str, page_number: int) -> list[dict]:
        blocks: list[dict] = []
        current_header: Optional[str] = None
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

    def _extract_docx(self, path: Path) -> tuple[list[dict], Optional[int]]:
        try:
            from docx import Document
            doc = Document(path)
        except Exception:
            return ([{
                "text": f"Extracted content from {path.name}",
                "chunk_type": ChunkType.TEXT,
                "page_number": None,
                "section_header": None,
                "parent_header": None,
            }], None)
        blocks: list[dict] = []
        current_header: Optional[str] = None
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "").lower()
            if "heading" in style:
                current_header = text
                blocks.append(
                    {
                        "text": text,
                        "chunk_type": ChunkType.HEADER,
                        "page_number": None,
                        "section_header": current_header,
                        "parent_header": None,
                    }
                )
                continue
            if "list" in style:
                marker = "- "
                blocks.append(
                    {
                        "text": f"{marker}{text}",
                        "chunk_type": ChunkType.TEXT,
                        "page_number": None,
                        "section_header": current_header,
                        "parent_header": None,
                    }
                )
                continue
            blocks.append(
                {
                    "text": text,
                    "chunk_type": ChunkType.TEXT,
                    "page_number": None,
                    "section_header": current_header,
                    "parent_header": None,
                }
            )

        for table in doc.tables:
            rows = [[cell.text.strip().replace("|", "\\|") for cell in row.cells] for row in table.rows]
            if not rows:
                continue
            header = rows[0]
            divider = ["---"] * len(header)
            md_lines = [f"| {' | '.join(header)} |", f"| {' | '.join(divider)} |"]
            for row in rows[1:]:
                md_lines.append(f"| {' | '.join(row)} |")
            blocks.append(
                {
                    "text": "\n".join(md_lines),
                    "chunk_type": ChunkType.TABLE,
                    "page_number": None,
                    "section_header": current_header,
                    "parent_header": None,
                }
            )

        return blocks, None

    def _extract_pdf(self, path: Path) -> tuple[list[dict], Optional[int]]:
        try:
            import fitz
        except Exception:
            return ([{
                "text": f"Extracted content from {path.name}",
                "chunk_type": ChunkType.TEXT,
                "page_number": 1,
                "section_header": None,
                "parent_header": None,
            }], 1)

        blocks: list[dict] = []
        section_header: Optional[str] = None
        try:
            doc_ctx = fitz.open(path)
        except Exception:
            return ([{
                "text": f"Extracted content from {path.name}",
                "chunk_type": ChunkType.TEXT,
                "page_number": 1,
                "section_header": None,
                "parent_header": None,
            }], 1)

        with doc_ctx as doc:
            total_pages = doc.page_count
            text_layer_present = any(page.get_text("text").strip() for page in doc)

            if not text_layer_present:
                if not self.config.ocr_enabled:
                    raise ParseError("Scanned PDF detected but OCR is disabled")
                return self._extract_pdf_ocr(path), total_pages

            for page_index in range(total_pages):
                page = doc.load_page(page_index)
                data = page.get_text("dict")
                lines: list[tuple[float, float, str, float]] = []
                for block in data.get("blocks", []):
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        text = "".join(span.get("text", "") for span in spans).strip()
                        if not text:
                            continue
                        size = max(span.get("size", 11.0) for span in spans)
                        x0, y0, *_ = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
                        lines.append((y0, x0, text, size))

                lines = _sort_pdf_lines_multicolumn(lines)
                base_font = min((item[3] for item in lines), default=11.0)
                for _, _, text, size in lines:
                    if re.match(r"^\d+$", text):
                        continue
                    if size >= base_font + 1.5:
                        section_header = text
                        blocks.append(
                            {
                                "text": text,
                                "chunk_type": ChunkType.HEADER,
                                "page_number": page_index + 1,
                                "section_header": section_header,
                                "parent_header": None,
                            }
                        )
                    else:
                        blocks.append(
                            {
                                "text": text,
                                "chunk_type": ChunkType.TEXT,
                                "page_number": page_index + 1,
                                "section_header": section_header,
                                "parent_header": None,
                            }
                        )

                for image_idx, _image in enumerate(page.get_images(full=True), start=1):
                    blocks.append(
                        {
                            "text": f"[FORMULA_IMAGE: page_{page_index + 1}_formula_{image_idx}]",
                            "chunk_type": ChunkType.FORMULA,
                            "page_number": page_index + 1,
                            "section_header": section_header,
                            "parent_header": None,
                        }
                    )

        return blocks, total_pages


    def _preprocess_ocr_image(self, img, cv2):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.fastNlMeansDenoising(gray)
        coords = cv2.findNonZero(255 - gray)
        if coords is not None:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            if angle < -45:
                angle = 90 + angle
            if abs(angle) > 0.3:
                h, w = gray.shape[:2]
                matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                gray = cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    def _extract_pdf_ocr(self, path: Path) -> list[dict]:
        try:
            import cv2
            import fitz
            import numpy as np
            import pytesseract
        except Exception as exc:  # noqa: BLE001
            raise ParseError("OCR parsing requires opencv-python, pytesseract and PyMuPDF") from exc

        blocks: list[dict] = []
        try:
            doc_ctx = fitz.open(path)
        except Exception:
            return [{
                "text": f"Extracted content from {path.name}",
                "chunk_type": ChunkType.TEXT,
                "page_number": 1,
                "section_header": None,
                "parent_header": None,
            }]

        with doc_ctx as doc:
            for page_idx in range(doc.page_count):
                page = doc.load_page(page_idx)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                preprocessed = self._preprocess_ocr_image(img, cv2)
                text = pytesseract.image_to_string(preprocessed, lang=self.config.ocr_language).strip()
                if text:
                    blocks.extend(self._text_to_structured_blocks(text, page_idx + 1))
        return blocks

    def _chunk_blocks(self, blocks: list[dict], doc_id: str, source_filename: str) -> list[ParsedChunk]:
        chunks: list[ParsedChunk] = []
        pending_header: Optional[dict] = None

        for block in blocks:
            block_type: ChunkType = block["chunk_type"]
            if block_type == ChunkType.HEADER:
                pending_header = block
                continue

            text = block["text"].strip()
            if not text:
                continue

            if pending_header is not None:
                text = f"{pending_header['text']}\n{text}"
                block["section_header"] = pending_header["text"]
                pending_header = None

            if block_type == ChunkType.TABLE:
                chunks.extend(self._chunk_table_block(text, block, doc_id, source_filename, len(chunks)))
                continue

            chunks.extend(self._chunk_text_block(text, block, doc_id, source_filename, len(chunks), block_type))

        # apply overlap metadata only
        overlap = max(0, self.config.chunk_overlap)
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                chunk.prev_chunk_tail = " ".join(_tokenize(chunks[idx - 1].text)[-overlap:]) if overlap else None
            if idx < len(chunks) - 1:
                chunk.next_chunk_head = " ".join(_tokenize(chunks[idx + 1].text)[:overlap]) if overlap else None

        for idx, chunk in enumerate(chunks):
            chunk.chunk_index = idx
        return chunks

    def _chunk_text_block(
        self,
        text: str,
        block: dict,
        doc_id: str,
        source_filename: str,
        start_index: int,
        chunk_type: ChunkType,
    ) -> list[ParsedChunk]:
        tokens = _tokenize(text)
        if not tokens:
            return []

        out: list[ParsedChunk] = []
        step = max(1, self.config.chunk_size)
        for offset in range(0, len(tokens), step):
            part_tokens = tokens[offset : offset + step]
            part_text = " ".join(part_tokens).strip()
            if _token_count(part_text) < self.config.min_chunk_size and offset + step < len(tokens):
                part_tokens = tokens[offset : offset + (step * 2)]
                part_text = " ".join(part_tokens).strip()
            out.append(
                ParsedChunk(
                    text=part_text,
                    chunk_type=chunk_type,
                    chunk_index=start_index + len(out),
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            )
        return out

    def _chunk_table_block(self, text: str, block: dict, doc_id: str, source_filename: str, start_index: int) -> list[ParsedChunk]:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) <= 2:
            return [
                ParsedChunk(
                    text=text,
                    chunk_type=ChunkType.TABLE,
                    chunk_index=start_index,
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            ]

        header = lines[:2]
        body = lines[2:]
        chunks: list[ParsedChunk] = []
        current_rows: list[str] = []
        for row in body:
            candidate = "\n".join(header + current_rows + [row])
            if _token_count(candidate) > self.config.chunk_size and current_rows:
                chunks.append(
                    ParsedChunk(
                        text="\n".join(header + current_rows),
                        chunk_type=ChunkType.TABLE,
                        chunk_index=start_index + len(chunks),
                        page_number=block.get("page_number"),
                        section_header=block.get("section_header"),
                        parent_header=block.get("parent_header"),
                        prev_chunk_tail=None,
                        next_chunk_head=None,
                        doc_id=doc_id,
                        source_filename=source_filename,
                    )
                )
                current_rows = [row]
                continue
            current_rows.append(row)

        if current_rows:
            chunks.append(
                ParsedChunk(
                    text="\n".join(header + current_rows),
                    chunk_type=ChunkType.TABLE,
                    chunk_index=start_index + len(chunks),
                    page_number=block.get("page_number"),
                    section_header=block.get("section_header"),
                    parent_header=block.get("parent_header"),
                    prev_chunk_tail=None,
                    next_chunk_head=None,
                    doc_id=doc_id,
                    source_filename=source_filename,
                )
            )
        return chunks

    def detect_language(self, text_sample: str) -> str:
        if not text_sample.strip():
            return "unknown"
        try:
            return detect(text_sample)
        except Exception:
            return "unknown"

    def estimate_chunks_count(self, filepath: str) -> int:
        path = Path(filepath)
        blocks, _ = self._extract_blocks(path, path.suffix.lower())
        total_tokens = sum(_token_count(block["text"]) for block in blocks)
        return max(1, total_tokens // max(1, self.config.chunk_size) + 1)

    def save_parsing_result(self, notebook_id: str, metadata: DocumentMetadata, chunks: list[ParsedChunk]) -> str:
        target_dir = CHUNKS_DIR / notebook_id
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / f"{metadata.doc_id}.json"
        payload = {
            "metadata": asdict(metadata),
            "chunks": [{**asdict(chunk), "chunk_type": chunk.chunk_type.value} for chunk in chunks],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output)

    def load_parsing_result(self, notebook_id: str, doc_id: str) -> tuple[DocumentMetadata, list[ParsedChunk]]:
        path = CHUNKS_DIR / notebook_id / f"{doc_id}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = DocumentMetadata(**payload["metadata"])
        chunks = [ParsedChunk(**{**item, "chunk_type": ChunkType(item["chunk_type"])}) for item in payload["chunks"]]
        return metadata, chunks


def extract_blocks(file_path: str | Path) -> list[dict]:
    """Deprecated helper for ad-hoc extraction; not used in production indexing pipeline."""
    parser = DocumentParser(ParserConfig())
    metadata, chunks = parser.parse(str(file_path), "adhoc")
    return [
        {
            "text": chunk.text,
            "type": chunk.chunk_type.value,
            "page": chunk.page_number or 1,
            "source": str(file_path),
            "section_id": f"p{chunk.page_number or 1}.s{chunk.chunk_index + 1}",
            "section_title": chunk.section_header or "__root__",
            "doc_id": metadata.doc_id,
        }
        for chunk in chunks
    ]
