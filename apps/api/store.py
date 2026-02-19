from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from uuid import uuid4

from .config import CHUNKS_DIR, DOCS_DIR, INDEX_DIR
from .schemas import ChatMessage, Note, Notebook, Source, now_iso
from .services.index_service import clear_notebook_blocks, index_source

DOCS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

DEMO_NOTEBOOK_ID = "00000000-0000-0000-0000-000000000001"


class InMemoryStore:
    def __init__(self) -> None:
        self.notebooks: dict[str, Notebook] = {}
        self.sources: dict[str, Source] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.notes: dict[str, list[Note]] = {}
        self.seed_data()

    def seed_data(self) -> None:
        if self.notebooks:
            return

        ts = now_iso()
        notebook = Notebook(
            id=DEMO_NOTEBOOK_ID,
            title="Техдоки: demo",
            created_at=ts,
            updated_at=ts,
        )
        self.notebooks[notebook.id] = notebook
        self.messages.setdefault(notebook.id, [])
        self.notes.setdefault(notebook.id, [])

        demo_dir = DOCS_DIR / notebook.id
        demo_dir.mkdir(parents=True, exist_ok=True)
        samples = [demo_dir / "sample-1.txt", demo_dir / "sample-2.txt"]
        for idx, sample in enumerate(samples, start=1):
            if not sample.exists():
                sample.write_text(f"Demo file #{idx}\nSection {idx}", encoding="utf-8")
            self.add_source_from_path(notebook.id, str(sample), indexed=True)

    def create_notebook(self, title: str) -> Notebook:
        ts = now_iso()
        notebook = Notebook(id=str(uuid4()), title=title, created_at=ts, updated_at=ts)
        self.notebooks[notebook.id] = notebook
        self.messages.setdefault(notebook.id, [])
        self.notes.setdefault(notebook.id, [])
        (DOCS_DIR / notebook.id).mkdir(parents=True, exist_ok=True)
        return notebook

    def update_notebook_title(self, notebook_id: str, title: str) -> Notebook | None:
        notebook = self.notebooks.get(notebook_id)
        if not notebook:
            return None
        notebook.title = title
        notebook.updated_at = now_iso()
        return notebook

    def delete_notebook(self, notebook_id: str) -> bool:
        if notebook_id not in self.notebooks:
            return False

        for source_id, source in list(self.sources.items()):
            if source.notebook_id != notebook_id:
                continue
            path = Path(source.file_path)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
            self.sources.pop(source_id, None)

        notebook_dir = DOCS_DIR / notebook_id
        if notebook_dir.exists() and notebook_dir.is_dir():
            for file in notebook_dir.glob("*"):
                if file.is_file():
                    file.unlink(missing_ok=True)
            notebook_dir.rmdir()

        del self.notebooks[notebook_id]
        self.messages.pop(notebook_id, None)
        self.notes.pop(notebook_id, None)
        clear_notebook_blocks(notebook_id)
        return True

    def add_source_from_path(self, notebook_id: str, path: str, indexed: bool = False) -> Source:
        file_path = Path(path)
        ext = file_path.suffix.lower().replace(".", "")
        file_type = ext if ext in {"pdf", "docx", "xlsx"} else "other"
        source = Source(
            id=str(uuid4()),
            notebook_id=notebook_id,
            filename=file_path.name,
            file_path=str(file_path),
            file_type=file_type,
            size_bytes=file_path.stat().st_size if file_path.exists() else 0,
            status="indexed" if indexed else "indexing",
            added_at=now_iso(),
        )
        self.sources[source.id] = source
        if indexed:
            return source
        thread = threading.Thread(target=self._index_source_sync, args=(source.id,), daemon=True)
        thread.start()
        return source

    async def save_upload(self, notebook_id: str, filename: str, content: bytes) -> Source:
        notebook_dir = DOCS_DIR / notebook_id
        notebook_dir.mkdir(parents=True, exist_ok=True)
        target = notebook_dir / f"{uuid4()}-{filename}"
        target.write_bytes(content)
        return self.add_source_from_path(notebook_id, str(target), indexed=False)

    def _index_source_sync(self, source_id: str) -> None:
        source = self.sources.get(source_id)
        if not source:
            return
        source.status = "indexing"
        try:
            asyncio.run(index_source(source.notebook_id, source.id, source.file_path))
            source.status = "indexed"
        except Exception:
            source.status = "failed"

    def add_message(self, notebook_id: str, role: str, content: str) -> ChatMessage:
        message = ChatMessage(
            id=str(uuid4()),
            notebook_id=notebook_id,
            role=role,
            content=content,
            created_at=now_iso(),
        )
        self.messages.setdefault(notebook_id, []).append(message)
        return message

    def clear_messages(self, notebook_id: str) -> None:
        self.messages[notebook_id] = []

    def add_note(self, notebook_id: str, title: str, content: str) -> Note:
        note = Note(id=str(uuid4()), notebook_id=notebook_id, title=title, content=content, created_at=now_iso())
        self.notes.setdefault(notebook_id, []).append(note)
        return note


store = InMemoryStore()
