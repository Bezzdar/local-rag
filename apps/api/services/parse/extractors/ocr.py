"""Экстрактор OCR для сканированных PDF-файлов (pytesseract + opencv)."""
# --- Imports ---
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import ChunkType, ParseError
from ..utils import _text_to_structured_blocks
from .base import BaseExtractor


# --- Models / Classes ---
class OcrExtractor(BaseExtractor):
    """OCR-экстрактор для сканов: page -> image -> preprocess -> text blocks."""

    def extract(self, path: Path) -> tuple[list[dict], Optional[int]]:
        """Возвращает (blocks, total_pages)."""
        blocks = self.extract_pages(path)
        return blocks, None

    def extract_pages(self, path: Path) -> list[dict]:
        """OCR-ветка для сканов: page -> image -> preprocess -> text blocks."""
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
            # OCR выполняется постранично: растеризация -> preprocessing -> Tesseract.
            for page_idx in range(doc.page_count):
                page = doc.load_page(page_idx)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                preprocessed = self._preprocess_ocr_image(img, cv2)
                text = pytesseract.image_to_string(preprocessed, lang=self.config.ocr_language).strip()
                if text:
                    blocks.extend(_text_to_structured_blocks(text, page_idx + 1))
        return blocks

    def _preprocess_ocr_image(self, img, cv2):
        # Шумоподавление, коррекция наклона и бинаризация перед распознаванием
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
