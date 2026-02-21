"""In-memory хранилище и оркестрация сущностей/индексации."""

# --- Imports ---
from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from uuid import uuid4

from .config import CHUNKS_DIR, DOCS_DIR, NOTEBOOKS_DB_DIR, EMBEDDING_BASE_URL, EMBEDDING_DIM, EMBEDDING_ENABLED, EMBEDDING_ENDPOINT, EMBEDDING_PROVIDER
from .schemas import ChatMessage, Note, Notebook, ParsingSettings, Source, now_iso
from .services.global_db import GlobalDB
from .services.index_service import index_source
from .services.embedding_service import EmbeddingConfig, EmbeddingEngine, EmbeddingProviderConfig
from .services.notebook_db import db_for_notebook

DOCS_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
NOTEBOOKS_DB_DIR.mkdir(parents=True, exist_ok=True)

DEMO_NOTEBOOK_ID = "00000000-0000-0000-0000-000000000001"

logger = logging.getLogger(__name__)

_global_db = GlobalDB()


# --- Основные блоки ---
class InMemoryStore:
    def __init__(self) -> None:
        self.notebooks: dict[str, Notebook] = {}
        self.sources: dict[str, Source] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.notes: dict[str, list[Note]] = {}
        self.chat_versions: dict[str, int] = {}
        self.parsing_settings: dict[str, ParsingSettings] = {}
        self._embedding_engine: EmbeddingEngine | None = None
        self.seed_data()

    def _get_embedding_engine(self) -> EmbeddingEngine:
        if self._embedding_engine is None:
            self._embedding_engine = EmbeddingEngine(
                EmbeddingConfig(
                    embedding_dim=EMBEDDING_DIM,
                    provider=EmbeddingProviderConfig(
                        base_url=EMBEDDING_BASE_URL,
                        model_name=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                        provider=EMBEDDING_PROVIDER,
                        endpoint=EMBEDDING_ENDPOINT,
                        enabled=EMBEDDING_ENABLED,
                        fallback_dim=EMBEDDING_DIM,
                    )
                )
            )
        return self._embedding_engine

    def reconfigure_embedding(self, provider: str, base_url: str, model_name: str) -> None:
        """Пересоздать движок эмбеддингов с новыми настройками провайдера/модели."""
        self._embedding_engine = EmbeddingEngine(
            EmbeddingConfig(
                embedding_dim=EMBEDDING_DIM,
                provider=EmbeddingProviderConfig(
                    base_url=base_url or EMBEDDING_BASE_URL,
                    model_name=model_name,
                    provider=provider or EMBEDDING_PROVIDER,
                    endpoint=EMBEDDING_ENDPOINT,
                    enabled=EMBEDDING_ENABLED,
                    fallback_dim=EMBEDDING_DIM,
                )
            )
        )
        from .services.search_service import reconfigure_engine
        reconfigure_engine(provider or EMBEDDING_PROVIDER, base_url or EMBEDDING_BASE_URL, model_name)

    def seed_data(self) -> None:
        # Восстановить ноутбуки из персистентного хранилища
        for nb_dict in _global_db.load_all_notebooks():
            notebook = Notebook(**nb_dict)
            self.notebooks[notebook.id] = notebook
            self.messages.setdefault(notebook.id, [])
            self.notes.setdefault(notebook.id, [])
            self.chat_versions.setdefault(notebook.id, 0)

        # Восстановить настройки парсинга
        for ps_dict in _global_db.load_all_parsing_settings():
            nb_id = ps_dict.pop("notebook_id")
            self.parsing_settings[nb_id] = ParsingSettings(**ps_dict)

        # Восстановить источники; исправить устаревшие состояния
        for src_dict in _global_db.load_all_sources():
            if src_dict["notebook_id"] not in self.notebooks:
                continue
            changed = False
            # Если файл физически удалён — обновить флаг
            if src_dict["has_docs"] and not Path(src_dict["file_path"]).exists():
                src_dict["has_docs"] = False
                changed = True
            # Индексация прервана рестартом — пометить как failed
            if src_dict["status"] == "indexing":
                src_dict["status"] = "failed"
                changed = True
            if changed:
                _global_db.upsert_source(src_dict)
            self.sources[src_dict["id"]] = Source(**src_dict)

        # Первый запуск: ноутбуков нет → создать демо
        if not self.notebooks:
            self._seed_demo()

    def _seed_demo(self) -> None:
        """Создаёт демо-ноутбук при первом запуске и персистирует его."""
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
        settings = ParsingSettings()
        self.parsing_settings[notebook.id] = settings
        _global_db.upsert_notebook(notebook.id, notebook.title, notebook.created_at, notebook.updated_at)
        _global_db.upsert_parsing_settings(
            notebook.id,
            settings.chunk_size,
            settings.chunk_overlap,
            settings.min_chunk_size,
            settings.ocr_enabled,
            settings.ocr_language,
        )

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
        settings = ParsingSettings()
        self.parsing_settings[notebook.id] = settings
        (DOCS_DIR / notebook.id).mkdir(parents=True, exist_ok=True)
        _global_db.upsert_notebook(notebook.id, notebook.title, notebook.created_at, notebook.updated_at)
        _global_db.upsert_parsing_settings(
            notebook.id,
            settings.chunk_size,
            settings.chunk_overlap,
            settings.min_chunk_size,
            settings.ocr_enabled,
            settings.ocr_language,
        )
        return notebook

    def update_notebook_title(self, notebook_id: str, title: str) -> Notebook | None:
        notebook = self.notebooks.get(notebook_id)
        if not notebook:
            return None
        notebook.title = title
        notebook.updated_at = now_iso()
        _global_db.upsert_notebook(notebook.id, notebook.title, notebook.created_at, notebook.updated_at)
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

        (NOTEBOOKS_DB_DIR / f"{notebook_id}.db").unlink(missing_ok=True)

        del self.notebooks[notebook_id]
        self.messages.pop(notebook_id, None)
        self.notes.pop(notebook_id, None)
        self.chat_versions.pop(notebook_id, None)
        self.parsing_settings.pop(notebook_id, None)
        _global_db.delete_notebook(notebook_id)
        return True

    def add_source_from_path(self, notebook_id: str, path: str, indexed: bool = False) -> Source:
        file_path = Path(path)
        ext = file_path.suffix.lower().replace(".", "")
        file_type = ext if ext in {"pdf", "docx", "xlsx"} else "other"
        settings = self.get_parsing_settings(notebook_id)
        should_index = indexed or settings.auto_parse_on_upload
        source = Source(
            id=str(uuid4()),
            notebook_id=notebook_id,
            filename=file_path.name,
            file_path=str(file_path),
            file_type=file_type,
            size_bytes=file_path.stat().st_size if file_path.exists() else 0,
            status="indexed" if indexed else ("indexing" if should_index else "new"),
            added_at=now_iso(),
            has_docs=file_path.exists(),
            has_parsing=indexed,
        )
        self.sources[source.id] = source
        _global_db.upsert_source(source.model_dump())
        if indexed:
            return source
        if should_index:
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
            metadata, _ = asyncio.run(
                index_source(
                    source.notebook_id,
                    source.id,
                    source.file_path,
                    parser_config=parser_config,
                    source_state=source.model_dump(),
                )
            )
            engine = self._get_embedding_engine()
            embedded_chunks = engine.embed_document_from_parsing(source.notebook_id, source.id)
            vector_ready = any(not item.embedding_failed for item in embedded_chunks)
            notebook_db = db_for_notebook(source.notebook_id)
            notebook_db.upsert_document(
                metadata=metadata,
                embedded_chunks=embedded_chunks,
                tags=[],
                is_enabled=source.is_enabled,
            )
            notebook_db.close()
            source.status = "indexed"
            source.has_parsing = True
            if vector_ready:
                source.embeddings_status = "available"
                source.index_warning = None
                logger.info("[index] %s indexed (vector+fts)", source.id)
            else:
                source.embeddings_status = "unavailable"
                source.index_warning = "indexed (text-only)"
                logger.warning("[index] %s indexed (text-only): embeddings unavailable", source.id)
            _global_db.upsert_source(source.model_dump())
        except Exception:
            logger.exception("[index] failed for source %s", source_id)
            source.status = "failed"
            try:
                _global_db.upsert_source(source.model_dump())
            except Exception:
                logger.exception("[persist] failed to persist failed status for source %s", source_id)

    def reparse_source(self, source_id: str) -> Source | None:
        source = self.sources.get(source_id)
        if not source:
            return None
        source.status = "indexing"
        _global_db.upsert_source(source.model_dump())
        thread = threading.Thread(target=self._index_source_sync, args=(source.id,), daemon=True)
        thread.start()
        return source

    def delete_source_fully(self, source_id: str) -> bool:
        """Delete source completely: file, parsing/chunks, DB records, and in-memory entry."""
        source = self.sources.get(source_id)
        if not source:
            return False
        # Delete physical file
        path = Path(source.file_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
        # Delete parsing/chunks JSON
        parsing_file = CHUNKS_DIR / source.notebook_id / f"{source.id}.json"
        parsing_file.unlink(missing_ok=True)
        # Remove from notebook SQLite DB
        try:
            notebook_db = db_for_notebook(source.notebook_id)
            notebook_db.conn.execute("DELETE FROM documents WHERE doc_id=?", (source.id,))
            notebook_db.conn.commit()
            notebook_db.close()
        except Exception:
            logger.exception("[delete_fully] failed to remove from notebook DB for source %s", source_id)
        # Remove from global DB and in-memory store
        _global_db.delete_source(source_id)
        self.sources.pop(source_id, None)
        return True

    def delete_source_file(self, source_id: str) -> bool:
        source = self.sources.get(source_id)
        if not source:
            return False
        path = Path(source.file_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
        source.has_docs = False
        _global_db.upsert_source(source.model_dump())
        return True

    def erase_source_data(self, source_id: str) -> bool:
        source = self.sources.get(source_id)
        if not source:
            return False
        parsing_file = CHUNKS_DIR / source.notebook_id / f"{source.id}.json"
        parsing_file.unlink(missing_ok=True)
        notebook_db = db_for_notebook(source.notebook_id)
        notebook_db.conn.execute("DELETE FROM documents WHERE doc_id=?", (source.id,))
        notebook_db.conn.commit()
        notebook_db.close()
        source.has_parsing = False
        source.status = "new"
        _global_db.upsert_source(source.model_dump())
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

    def persist_source(self, source_id: str) -> None:
        """Сохранить текущее состояние источника в персистентное хранилище."""
        source = self.sources.get(source_id)
        if source:
            _global_db.upsert_source(source.model_dump())

    def get_parsing_settings(self, notebook_id: str) -> ParsingSettings:
        return self.parsing_settings.setdefault(notebook_id, ParsingSettings())

    def update_parsing_settings(self, notebook_id: str, payload: ParsingSettings) -> ParsingSettings:
        self.parsing_settings[notebook_id] = payload
        _global_db.upsert_parsing_settings(
            notebook_id,
            payload.chunk_size,
            payload.chunk_overlap,
            payload.min_chunk_size,
            payload.ocr_enabled,
            payload.ocr_language,
            payload.auto_parse_on_upload,
        )
        return payload

    def sync_source_enabled(self, source_id: str, enabled: bool) -> None:
        source = self.sources.get(source_id)
        if not source:
            return
        notebook_db = db_for_notebook(source.notebook_id)
        notebook_db.set_document_enabled(source_id, enabled)
        notebook_db.close()

    def duplicate_notebook(self, notebook_id: str) -> Notebook | None:
        """Дублировать ноутбук со всеми источниками, парсингом и базой данных."""
        import shutil
        original = self.notebooks.get(notebook_id)
        if not original:
            return None

        # Создать новый ноутбук
        new_title = f"Копия: {original.title}"
        new_nb = self.create_notebook(new_title)
        new_nb_id = new_nb.id

        # Скопировать настройки парсинга
        orig_settings = self.get_parsing_settings(notebook_id)
        self.update_parsing_settings(new_nb_id, orig_settings)

        # Построить маппинг old_source_id -> new_source_id
        orig_sources = [s for s in self.sources.values() if s.notebook_id == notebook_id]
        id_map: dict[str, str] = {}
        for src in orig_sources:
            new_src_id = str(uuid4())
            id_map[src.id] = new_src_id

        # Скопировать файлы документов и создать новые записи источников
        new_nb_docs_dir = DOCS_DIR / new_nb_id
        new_nb_docs_dir.mkdir(parents=True, exist_ok=True)
        new_nb_chunks_dir = CHUNKS_DIR / new_nb_id
        new_nb_chunks_dir.mkdir(parents=True, exist_ok=True)

        for src in orig_sources:
            new_src_id = id_map[src.id]
            orig_path = Path(src.file_path)
            new_path = new_nb_docs_dir / orig_path.name

            # Копировать физический файл (если существует)
            if orig_path.exists():
                shutil.copy2(str(orig_path), str(new_path))

            # Копировать JSON-файл чанков (если существует)
            orig_chunks_file = CHUNKS_DIR / notebook_id / f"{src.id}.json"
            new_chunks_file = new_nb_chunks_dir / f"{new_src_id}.json"
            if orig_chunks_file.exists():
                shutil.copy2(str(orig_chunks_file), str(new_chunks_file))

            # Создать новую запись источника
            new_source = Source(
                id=new_src_id,
                notebook_id=new_nb_id,
                filename=src.filename,
                file_path=str(new_path),
                file_type=src.file_type,
                size_bytes=src.size_bytes,
                status=src.status if orig_path.exists() else "new",
                added_at=now_iso(),
                is_enabled=src.is_enabled,
                has_docs=new_path.exists(),
                has_parsing=src.has_parsing and orig_chunks_file.exists(),
                embeddings_status=src.embeddings_status,
                index_warning=src.index_warning,
                individual_config=dict(src.individual_config),
            )
            self.sources[new_src_id] = new_source
            _global_db.upsert_source(new_source.model_dump())

        # Скопировать и обновить SQLite базу данных ноутбука
        orig_db_path = NOTEBOOKS_DB_DIR / f"{notebook_id}.db"
        new_db_path = NOTEBOOKS_DB_DIR / f"{new_nb_id}.db"
        if orig_db_path.exists():
            shutil.copy2(str(orig_db_path), str(new_db_path))
            # Обновить ссылки на источники в новой БД
            import sqlite3
            conn = sqlite3.connect(str(new_db_path))
            try:
                for old_id, new_id in id_map.items():
                    orig_src = next((s for s in orig_sources if s.id == old_id), None)
                    new_file_path = str(new_nb_docs_dir / Path(orig_src.file_path).name) if orig_src else ""
                    # Обновить таблицу documents
                    conn.execute(
                        "UPDATE documents SET doc_id=?, source_id=?, filepath=? WHERE doc_id=?",
                        (new_id, new_id, new_file_path, old_id),
                    )
                    # Обновить таблицу chunks
                    conn.execute(
                        "UPDATE chunks SET doc_id=? WHERE doc_id=?",
                        (new_id, old_id),
                    )
                    # Обновить таблицу document_tags
                    conn.execute(
                        "UPDATE document_tags SET doc_id=? WHERE doc_id=?",
                        (new_id, old_id),
                    )
                conn.commit()
            finally:
                conn.close()

        return new_nb

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
