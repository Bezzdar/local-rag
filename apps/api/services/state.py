"""In-memory хранилище: структуры данных, геттеры/сеттеры состояния приложения."""
# --- Imports ---
from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from ..config import CITATIONS_DIR, NOTES_DIR
from ..schemas import ChatMessage, CitationLocation, GlobalNote, SavedCitation, now_iso


logger = logging.getLogger(__name__)


# --- Models / Classes ---
class InMemoryState:
    """Чистое in-memory хранилище: словари состояния и простые геттеры/сеттеры.

    Не вызывает внешние сервисы (GlobalDB, NotebookDB, index_service и т.д.).
    """

    def __init__(self) -> None:
        from ..schemas import Notebook, ParsingSettings, Source
        self.notebooks: dict[str, Notebook] = {}
        self.sources: dict[str, Source] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.chat_versions: dict[str, int] = {}
        self.parsing_settings: dict[str, ParsingSettings] = {}

    def get_source_order_map(self, notebook_id: str) -> dict[str, int]:
        """Return mapping of source_id → sequential display number (1-based) for the notebook."""
        nb_sources = sorted(
            [s for s in self.sources.values() if s.notebook_id == notebook_id],
            key=lambda s: (s.sort_order, s.added_at),
        )
        return {s.id: idx for idx, s in enumerate(nb_sources, start=1)}

    def get_parsing_settings(self, notebook_id: str):
        """Возвращает настройки парсинга для ноутбука, создавая дефолтные при отсутствии."""
        from ..schemas import ParsingSettings
        return self.parsing_settings.setdefault(notebook_id, ParsingSettings())

    def add_message(self, notebook_id: str, role: str, content: str) -> ChatMessage:
        """Добавляет сообщение в историю чата ноутбука."""
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
        """Очищает историю чата и инкрементирует версию."""
        self.messages[notebook_id] = []
        self.chat_versions[notebook_id] = self.chat_versions.get(notebook_id, 0) + 1
        return self.chat_versions[notebook_id]

    def get_chat_version(self, notebook_id: str) -> int:
        return self.chat_versions.get(notebook_id, 0)

    # --- Saved Citations (persistent, per-notebook) ---

    def _citation_path(self, notebook_id: str, citation_id: str) -> Path:
        return CITATIONS_DIR / notebook_id / f"{citation_id}.json"

    def list_saved_citations(self, notebook_id: str) -> list[SavedCitation]:
        nb_dir = CITATIONS_DIR / notebook_id
        if not nb_dir.exists():
            return []
        results = []
        for f in sorted(nb_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append(SavedCitation(**data))
            except Exception:
                logger.exception("Failed to load citation file %s", f)
        results.sort(key=lambda c: c.created_at)
        return results

    def save_citation(
        self,
        notebook_id: str,
        source_id: str,
        filename: str,
        doc_order: int,
        chunk_text: str,
        page: int | None,
        sheet: str | None,
        source_notebook_id: str,
        source_type: str = "notebook",
    ) -> SavedCitation:
        citation = SavedCitation(
            id=str(uuid4()),
            notebook_id=notebook_id,
            source_id=source_id,
            filename=filename,
            doc_order=doc_order,
            chunk_text=chunk_text,
            location=CitationLocation(page=page, sheet=sheet),
            created_at=now_iso(),
            source_notebook_id=source_notebook_id,
            source_type=source_type,
        )
        nb_dir = CITATIONS_DIR / notebook_id
        nb_dir.mkdir(parents=True, exist_ok=True)
        self._citation_path(notebook_id, citation.id).write_text(
            citation.model_dump_json(indent=2), encoding="utf-8"
        )
        return citation

    def delete_saved_citation(self, notebook_id: str, citation_id: str) -> bool:
        path = self._citation_path(notebook_id, citation_id)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False

    def _delete_citations_for_source(self, notebook_id: str, source_id: str) -> None:
        """Remove all saved citations referencing a deleted source."""
        nb_dir = CITATIONS_DIR / notebook_id
        if not nb_dir.exists():
            return
        for f in nb_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("source_id") == source_id:
                    f.unlink(missing_ok=True)
            except Exception:
                logger.exception("Failed to check citation file %s", f)

    # --- Global Notes (persistent, cross-notebook) ---

    def _note_path(self, note_id: str) -> Path:
        return NOTES_DIR / f"{note_id}.json"

    def list_global_notes(self) -> list[GlobalNote]:
        results = []
        for f in sorted(NOTES_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append(GlobalNote(**data))
            except Exception:
                logger.exception("Failed to load note file %s", f)
        results.sort(key=lambda n: n.created_at)
        return results

    def save_global_note(
        self,
        content: str,
        source_notebook_id: str,
        source_notebook_title: str,
        source_refs: list[dict] | None = None,
    ) -> GlobalNote:
        note = GlobalNote(
            id=str(uuid4()),
            content=content,
            source_notebook_id=source_notebook_id,
            source_notebook_title=source_notebook_title,
            created_at=now_iso(),
            source_refs=source_refs or [],
        )
        self._note_path(note.id).write_text(note.model_dump_json(indent=2), encoding="utf-8")
        return note

    def delete_global_note(self, note_id: str) -> bool:
        path = self._note_path(note_id)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False
