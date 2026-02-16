from __future__ import annotations

import asyncio
import random
from pathlib import Path
from uuid import uuid4

from .schemas import (
    ChatMessage,
    Citation,
    CitationLocation,
    Note,
    Notebook,
    Source,
    now_iso,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DOCS_DIR = DATA_DIR / "docs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class InMemoryStore:
    def __init__(self) -> None:
        self.notebooks: dict[str, Notebook] = {}
        self.sources: dict[str, Source] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.notes: dict[str, list[Note]] = {}
        self.seed()

    def seed(self) -> None:
        if self.notebooks:
            return
        notebook = self.create_notebook("Техническая документация")
        candidates = list(DOCS_DIR.glob("**/*"))
        files = [p for p in candidates if p.is_file()][:2]
        if not files:
            for i in range(2):
                sample = UPLOAD_DIR / f"sample-{i+1}.txt"
                sample.write_text(f"Sample content #{i+1}", encoding="utf-8")
                files.append(sample)
        for f in files:
            self.add_source_from_path(notebook.id, str(f), indexed=True)

    def create_notebook(self, title: str) -> Notebook:
        nb = Notebook(id=str(uuid4()), title=title, created_at=now_iso(), updated_at=now_iso())
        self.notebooks[nb.id] = nb
        self.messages[nb.id] = []
        self.notes[nb.id] = []
        return nb

    def add_source_from_path(self, notebook_id: str, path: str, indexed: bool = False) -> Source:
        p = Path(path)
        ext = p.suffix.lower().lstrip(".")
        file_type = ext if ext in {"pdf", "docx", "xlsx"} else "other"
        source = Source(
            id=str(uuid4()),
            notebook_id=notebook_id,
            filename=p.name,
            file_path=str(p),
            file_type=file_type,  # type: ignore[arg-type]
            size_bytes=p.stat().st_size if p.exists() else 0,
            status="indexed" if indexed else "indexing",
            added_at=now_iso(),
        )
        self.sources[source.id] = source
        if not indexed:
            asyncio.create_task(self._mark_indexed(source.id))
        return source

    async def save_upload(self, notebook_id: str, filename: str, content: bytes) -> Source:
        target = UPLOAD_DIR / f"{uuid4()}-{filename}"
        target.write_bytes(content)
        return self.add_source_from_path(notebook_id, str(target), indexed=False)

    async def _mark_indexed(self, source_id: str) -> None:
        await asyncio.sleep(1.5)
        src = self.sources.get(source_id)
        if src:
            src.status = "indexed"

    def add_message(self, notebook_id: str, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(
            id=str(uuid4()),
            notebook_id=notebook_id,
            role=role,  # type: ignore[arg-type]
            content=content,
            created_at=now_iso(),
        )
        self.messages.setdefault(notebook_id, []).append(msg)
        return msg

    def build_mock_answer(self, question: str, mode: str) -> str:
        preface = {
            "qa": "Ответ по документам:",
            "draft": "Черновик раздела:",
            "table": "Табличное резюме:",
            "summarize": "Краткая сводка:",
        }.get(mode, "Ответ:")
        return f"{preface} {question}. Сформировано локально через mock-пайплайн c интерфейсом для последующей интеграции Ollama."

    def pick_citations(self, notebook_id: str, selected_source_ids: list[str] | None = None) -> list[Citation]:
        all_sources = [s for s in self.sources.values() if s.notebook_id == notebook_id]
        if selected_source_ids:
            selected = [s for s in all_sources if s.id in selected_source_ids]
        else:
            selected = all_sources
        random.shuffle(selected)
        citations: list[Citation] = []
        for src in selected[:5]:
            citations.append(
                Citation(
                    id=str(uuid4()),
                    notebook_id=notebook_id,
                    source_id=src.id,
                    filename=src.filename,
                    location=CitationLocation(page=random.randint(1, 10), paragraph=random.randint(1, 8)),
                    snippet=f"Фрагмент из {src.filename}: релевантный технический абзац.",
                    score=round(random.uniform(0.65, 0.98), 2),
                )
            )
        return citations


store = InMemoryStore()
