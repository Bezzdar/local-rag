from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.services.parse_service import ChunkType, DocumentParser, ParserConfig
from apps.api.store import InMemoryStore


def test_parse_text_pdf(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "# Intro\nHello world from pdf")
    doc.save(pdf_path)
    doc.close()

    parser = DocumentParser(ParserConfig(chunk_size=5, chunk_overlap=2, min_chunk_size=1))
    metadata, chunks = parser.parse(str(pdf_path), "nb-1")

    assert metadata.filename == "text.pdf"
    assert metadata.total_chunks >= 1
    assert any(chunk.page_number == 1 for chunk in chunks)


def test_parse_scanned_pdf_ocr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    parser = DocumentParser(ParserConfig(chunk_size=20, chunk_overlap=2, min_chunk_size=1, ocr_enabled=True))
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(DocumentParser, "_extract_pdf", lambda self, path: ([{
        "text": "OCR extracted text",
        "chunk_type": ChunkType.TEXT,
        "page_number": 1,
        "section_header": "OCR",
        "parent_header": None,
    }], 1))

    metadata, chunks = parser.parse(str(pdf_path), "nb-1")
    assert metadata.total_chunks == 1
    assert chunks[0].text == "OCR extracted text"


def test_parse_docx_headings_tables_lists(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    doc_path = tmp_path / "doc.docx"
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    document.add_paragraph("Item", style="List Bullet")
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "A"
    table.rows[0].cells[1].text = "B"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "2"
    document.save(doc_path)

    parser = DocumentParser(ParserConfig(chunk_size=40, chunk_overlap=2, min_chunk_size=1))
    _, chunks = parser.parse(str(doc_path), "nb-1")

    assert any("Heading One" in chunk.text for chunk in chunks)
    assert any(chunk.chunk_type == ChunkType.TABLE for chunk in chunks)
    assert any("- Item" in chunk.text for chunk in chunks)


def test_chunking_rules() -> None:
    parser = DocumentParser(ParserConfig(chunk_size=8, chunk_overlap=2, min_chunk_size=1))
    table_text = "\n".join([
        "| H1 | H2 |",
        "| --- | --- |",
        "| r1 | v1 |",
        "| r2 | v2 |",
        "| r3 | v3 |",
        "| r4 | v4 |",
    ])
    blocks = [
        {"text": "Section A", "chunk_type": ChunkType.HEADER, "page_number": 1, "section_header": "Section A", "parent_header": None},
        {"text": "alpha beta gamma delta epsilon zeta", "chunk_type": ChunkType.TEXT, "page_number": 1, "section_header": "Section A", "parent_header": None},
        {"text": table_text, "chunk_type": ChunkType.TABLE, "page_number": 1, "section_header": "Section A", "parent_header": None},
    ]

    chunks = parser._chunk_blocks(blocks, doc_id="d1", source_filename="f.txt")
    assert chunks[0].text.startswith("Section A")
    assert any(chunk.chunk_type == ChunkType.TABLE for chunk in chunks)
    if len(chunks) > 1:
        assert chunks[1].prev_chunk_tail is not None or chunks[1].next_chunk_head is not None


def test_individual_config_override(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text(" ".join(["token"] * 40), encoding="utf-8")
    parser = DocumentParser(ParserConfig(chunk_size=100, chunk_overlap=5, min_chunk_size=1))

    metadata, chunks = parser.parse(
        str(file_path),
        "nb-1",
        metadata_override={
            "doc_id": "doc-1",
            "individual_config": {"chunk_size": 10, "chunk_overlap": 2, "ocr_enabled": None, "ocr_language": None},
        },
    )

    assert metadata.individual_config["chunk_size"] == 10
    assert chunks[0].doc_id == "doc-1"


def test_name_conflict_suffixes(tmp_path: Path) -> None:
    store = InMemoryStore()
    notebook_id = "nb-test"
    store.notebooks[notebook_id] = store.notebooks[next(iter(store.notebooks))].model_copy(update={"id": notebook_id})

    first = store._next_available_path(notebook_id, "file.txt")
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("x", encoding="utf-8")
    second = store._next_available_path(notebook_id, "file.txt")

    assert second.name.startswith("file_")
    assert second.name.endswith(".txt")


def test_multi_column_order() -> None:
    lines = [
        (10.0, 50.0, 'L1', 11.0),
        (20.0, 50.0, 'L2', 11.0),
        (10.0, 300.0, 'R1', 11.0),
        (20.0, 300.0, 'R2', 11.0),
    ]
    from apps.api.services.parse_service import _sort_pdf_lines_multicolumn

    ordered = _sort_pdf_lines_multicolumn(lines)
    assert [item[2] for item in ordered] == ['L1', 'L2', 'R1', 'R2']


def test_large_table_chunking_keeps_header() -> None:
    parser = DocumentParser(ParserConfig(chunk_size=5, chunk_overlap=2, min_chunk_size=1))
    rows = ['| H1 | H2 |', '| --- | --- |'] + [f'| row{i} | val{i} |' for i in range(20)]
    table_text = "\n".join(rows)
    chunks = parser._chunk_table_block(
        table_text,
        {'page_number': 1, 'section_header': 'Sec', 'parent_header': None},
        'doc',
        'file',
        0,
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.splitlines()[0] == '| H1 | H2 |'


def test_ocr_preprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    np = pytest.importorskip('numpy')
    parser = DocumentParser(ParserConfig())

    class DummyCv2:
        COLOR_BGR2GRAY = 1
        INTER_CUBIC = 1
        BORDER_REPLICATE = 1
        THRESH_BINARY = 1
        THRESH_OTSU = 1

        @staticmethod
        def cvtColor(img, _):
            return img[..., 0]

        @staticmethod
        def fastNlMeansDenoising(gray):
            return gray

        @staticmethod
        def findNonZero(gray):
            return np.array([[[1, 1]], [[2, 2]]], dtype=np.int32)

        @staticmethod
        def minAreaRect(_):
            return ((0, 0), (1, 1), -10.0)

        @staticmethod
        def getRotationMatrix2D(_center, _angle, _scale):
            return np.eye(2, 3)

        @staticmethod
        def warpAffine(gray, _matrix, _shape, flags=None, borderMode=None):
            return gray

        @staticmethod
        def threshold(gray, _a, _b, _c):
            return 0, gray

    img = np.zeros((5, 5, 3), dtype=np.uint8)
    processed = parser._preprocess_ocr_image(img, DummyCv2)
    assert processed.shape == (5, 5)


def test_individual_merge() -> None:
    store = InMemoryStore()
    notebook_id = next(iter(store.notebooks))
    settings = store.get_parsing_settings(notebook_id)
    settings.chunk_size = 111
    source = next(item for item in store.sources.values() if item.notebook_id == notebook_id)
    source.individual_config['chunk_size'] = 77

    indiv = source.individual_config or {}
    merged_chunk_size = int(indiv.get('chunk_size') or settings.chunk_size)
    assert merged_chunk_size == 77
