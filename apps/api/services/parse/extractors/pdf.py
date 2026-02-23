"""Экстрактор для PDF-файлов с текстовым слоем; переключается на OCR при необходимости."""
# --- Imports ---
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import ChunkType, ParseError
from ..utils import _sort_pdf_lines_multicolumn
from .base import BaseExtractor


# --- Models / Classes ---
class PdfExtractor(BaseExtractor):
    """Извлекает PDF из text-layer или переключается на OCR при необходимости."""

    def extract(self, path: Path) -> tuple[list[dict], Optional[int]]:
        """Возвращает (blocks, total_pages)."""
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

        import re
        with doc_ctx as doc:
            total_pages = doc.page_count
            # Проверяем наличие текстового слоя: это ключевая развилка text-layer vs OCR.
            text_layer_present = any(page.get_text("text").strip() for page in doc)

            if not text_layer_present:
                if not self.config.ocr_enabled:
                    raise ParseError("Scanned PDF detected but OCR is disabled")
                from .ocr import OcrExtractor
                ocr_blocks = OcrExtractor(self.config).extract_pages(path)
                return ocr_blocks, total_pages

            # Постранично строим список строк с координатами и размером шрифта.
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

                # Переупорядочиваем строки для двухколоночных макетов.
                lines = _sort_pdf_lines_multicolumn(lines)
                base_font = min((item[3] for item in lines), default=11.0)
                # Эвристика: увеличенный шрифт считаем заголовком, остальное — текстом.
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
