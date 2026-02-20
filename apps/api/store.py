"""In-memory хранилище и оркестрация сущностей/индексации."""

# --- Imports ---
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from uuid import uuid4

from .config import BASE_DIR, CHUNKS_DIR, DOCS_DIR
from .schemas import ChatMessage, Note, Notebook, ParsingSettings, Source, now_iso
from .services.index_service import clear_notebook_blocks, index_source, remove_source_blocks

DOCS_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

DEMO_NOTEBOOK_ID = "00000000-0000-0000-0000-000000000001"


# --- Основные блоки ---
class InMemoryStore:
    def __init__(self) -> None:
        self.notebooks: dict[str, Notebook] = {}
        self.sources: dict[str, Source] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.notes: dict[str, list[Note]] = {}
        self.chat_versions: dict[str, int] = {}
        self.parsing_settings: dict[str, ParsingSettings] = {}
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
        self.chat_versions.setdefault(notebook.id, 0)
        self.parsing_settings.setdefault(notebook.id, ParsingSettings())

        demo_dir = DOCS_DIR / notebook.id
        demo_dir.mkdir(parents=True, exist_ok=True)
        samples = [demo_dir / "sample-1.txt", demo_dir / "sample-2.txt"]
        for idx, sample in enumerate(samples, start=1):
            if not sample.exists():
                sample.write_text(f"Demo file #{idx}\nSection {idx}", encoding="utf-8")
            self.add_source_from_path(notebook.id, str(sample), indexed=True)

    def _next_available_path(self, notebook_id: str, filename: str) -> Path:
        notebook_dir = DOCS_DIR / notebook_id
        notebook_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        candidate = notebook_dir / filename
        counter = 1
        while candidate.exists():
            candidate = notebook_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        return candidate

    def create_notebook(self, title: str) -> Notebook:
        ts = now_iso()
        notebook = Notebook(id=str(uuid4()), title=title, created_at=ts, updated_at=ts)
        self.notebooks[notebook.id] = notebook
        self.messages.setdefault(notebook.id, [])
        self.notes.setdefault(notebook.id, [])
        self.chat_versions.setdefault(notebook.id, 0)
        self.parsing_settings.setdefault(notebook.id, ParsingSettings())
        (DOCS_DIR / notebook.id).mkdir(parents=True, exist_ok=True)
        (CHUNKS_DIR / notebook.id).mkdir(parents=True, exist_ok=True)
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

        for directory in (DOCS_DIR / notebook_id, CHUNKS_DIR / notebook_id):
            if directory.exists() and directory.is_dir():
                for file in directory.glob("*"):
                    if file.is_file():
                        file.unlink(missing_ok=True)
                directory.rmdir()

        del self.notebooks[notebook_id]
        self.messages.pop(notebook_id, None)
        self.notes.pop(notebook_id, None)
        self.chat_versions.pop(notebook_id, None)
        self.parsing_settings.pop(notebook_id, None)
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
            has_docs=file_path.exists(),
            has_parsing=indexed,
            has_base=indexed,
        )
        self.sources[source.id] = source
        if indexed:
            return source
        thread = threading.Thread(target=self._index_source_sync, args=(source.id,), daemon=True)
        thread.start()
        return source

    async def save_upload(self, notebook_id: str, filename: str, content: bytes) -> Source:
        target = self._next_available_path(notebook_id, filename)
        target.write_bytes(content)
        return self.add_source_from_path(notebook_id, str(target), indexed=False)

    def _index_source_sync(self, source_id: str) -> None:
        source = self.sources.get(source_id)
        if not source:
            return
        source.status = "indexing"
        try:
            global_cfg = self.get_parsing_settings(source.notebook_id)
            indiv = source.individual_config or {}
            parser_config = {
                "chunk_size": int(indiv.get("chunk_size") or global_cfg.chunk_size),
                "chunk_overlap": int(indiv.get("chunk_overlap") or global_cfg.chunk_overlap),
                "min_chunk_size": global_cfg.min_chunk_size,
                "ocr_enabled": bool(global_cfg.ocr_enabled if indiv.get("ocr_enabled") is None else indiv.get("ocr_enabled")),
                "ocr_language": str(indiv.get("ocr_language") or global_cfg.ocr_language),
            }
            asyncio.run(index_source(source.notebook_id, source.id, source.file_path, parser_config=parser_config, source_state=source.model_dump()))
            source.status = "indexed"
            source.has_parsing = True
            source.has_base = True
        except Exception:
            source.status = "failed"


    def reparse_source(self, source_id: str) -> Source | None:
        source = self.sources.get(source_id)
        if not source:
            return None
        thread = threading.Thread(target=self._index_source_sync, args=(source.id,), daemon=True)
        thread.start()
        return source

    def delete_source_file(self, source_id: str) -> bool:
        source = self.sources.get(source_id)
        if not source:
            return False
        path = Path(source.file_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
        source.has_docs = False
        return True

    def erase_source_data(self, source_id: str) -> bool:
        source = self.sources.get(source_id)
        if not source:
            return False
        remove_source_blocks(source.notebook_id, source_id)
        parsing_file = CHUNKS_DIR / source.notebook_id / f"{source.id}.json"
        parsing_file.unlink(missing_ok=True)
        base_file = BASE_DIR / source.notebook_id / f"{source.id}.json"
        base_file.unlink(missing_ok=True)
        source.has_parsing = False
        source.has_base = False
        source.status = "new"
        return True

    def delete_all_source_files(self, notebook_id: str) -> int:
        removed = 0
        for source in self.sources.values():
            if source.notebook_id != notebook_id:
                continue
            if source.has_docs:
                self.delete_source_file(source.id)
                removed += 1
        return removed


    def get_parsing_settings(self, notebook_id: str) -> ParsingSettings:
        return self.parsing_settings.setdefault(notebook_id, ParsingSettings())

    def update_parsing_settings(self, notebook_id: str, payload: ParsingSettings) -> ParsingSettings:
        self.parsing_settings[notebook_id] = payload
        return payload

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

    def clear_messages(self, notebook_id: str) -> int:
        self.messages[notebook_id] = []
        self.chat_versions[notebook_id] = self.chat_versions.get(notebook_id, 0) + 1
        return self.chat_versions[notebook_id]

    def get_chat_version(self, notebook_id: str) -> int:
        return self.chat_versions.get(notebook_id, 0)

    def add_note(self, notebook_id: str, title: str, content: str) -> Note:
        note = Note(id=str(uuid4()), notebook_id=notebook_id, title=title, content=content, created_at=now_iso())
        self.notes.setdefault(notebook_id, []).append(note)
        return note


store = InMemoryStore()
