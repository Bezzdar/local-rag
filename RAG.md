# RAG.md — файлы логики полного RAG-контура

Ниже перечислены файлы, которые участвуют в цепочке: **загрузка файла в notebook → парсинг → чанкинг → эмбеддинг → запись в векторное хранилище → retrieval → подготовка и выдача ответа (включая SSE)**.

## 1) Вход API и оркестрация notebook/source

| Файл | Функциональное назначение |
|---|---|
| `apps/api/main.py` | Инициализация FastAPI-приложения, подключение роутеров и middleware; точка входа backend API. |
| `apps/api/routers/notebooks.py` | Эндпоинты управления notebook-сущностями (создание, чтение, удаление) и связанного состояния. |
| `apps/api/routers/sources.py` | Эндпоинты загрузки/удаления источников, запуска/контроля индексации и статусов источников. |
| `apps/api/store.py` | Центральная in-memory оркестрация notebooks/sources/messages/notes и вызовов индексации. |
| `apps/api/schemas.py` | Pydantic-контракты для запросов/ответов, используемых в upload/index/chat-контурах. |
| `apps/api/config.py` | Пути к `data/docs`, `data/parsing`, `data/notebooks` и другие backend-настройки, влияющие на pipeline. |

## 2) Парсинг и подготовка текстовых блоков

| Файл | Функциональное назначение |
|---|---|
| `apps/api/services/parse_service.py` | Backend-сервис парсинга документов, нормализации и подготовки структурированных чанков/метаданных. |
| `packages/rag_core/parsers/text_extraction.py` | Извлечение текста из PDF/DOCX/TXT и др., очистка, секционирование, формирование `TextBlock`. |
| `packages/rag_core/parsers/preprocessing.py` | Предобработка текста для более качественного последующего chunking/retrieval. |
| `packages/rag_core/parsers/ner_extraction.py` | Извлечение сущностей для enrichment и дополнительной аналитики текста. |

## 3) Чанкинг, эмбеддинги, индексация и векторная БД

| Файл | Функциональное назначение |
|---|---|
| `apps/api/services/index_service.py` | Координация индексации источника: вызов парсера, преобразование блоков в индексируемую структуру notebook-уровня. |
| `apps/api/services/embedding_service.py` | Генерация/подготовка эмбеддингов (или совместимого представления) для search-пайплайна API. |
| `packages/rag_core/app/chunk_manager.py` | Семантический/структурный chunking (включая parent/child) и работа с chunk-артефактами. |
| `packages/rag_core/app/chunk_editor.py` | Вспомогательная постобработка/редактирование сформированных чанков. |
| `packages/rag_core/app/engine.py` | Сквозной orchestrator legacy-контура: extract → chunk → embed → сохранение/работа с индексом. |
| `packages/rag_core/app/config.py` | Конфигурация параметров RAG-ядра, путей и режимов индексирования/поиска. |
| `packages/rag_core/app/search_tools.py` | Инструменты ранжирования и утилиты retrieval, используемые на этапе индекса/поиска. |

## 4) Retrieval, сборка ответа, генерация и стриминг

| Файл | Функциональное назначение |
|---|---|
| `apps/api/routers/chat.py` | HTTP/SSE-эндпоинты чата; запуск retrieval, потоковая выдача токенов/цитат и финального статуса. |
| `apps/api/services/search_service.py` | Поиск релевантных чанков по notebook-индексу, формирование цитирований и evidence-данных. |
| `apps/api/services/chat_modes.py` | Логика режимов чата и сборка ответа в зависимости от сценария работы ассистента. |
| `apps/api/services/model_chat.py` | Формирование истории, генерация ответа моделью и стриминг ответа (если включён model-backed режим). |
| `apps/api/routers/llm.py` | API-контур управления LLM-настройками/провайдерами, влияющими на этап генерации ответа. |
| `packages/rag_core/app/search_engine.py` | Ядро retrieval/ранжирования в legacy-контуре для отбора релевантного контекста. |
| `packages/rag_core/app/async_search.py` | Асинхронные сценарии поиска и вспомогательная логика для retrieval-контура. |
| `packages/rag_core/app/llm_generic.py` | Унифицированный интерфейс вызова LLM в ядре RAG и сборки модельного ответа. |
| `packages/rag_core/app/math_engine.py` | Математические функции/метрики, используемые в ранжировании и вычислениях поиска. |
| `packages/rag_core/app/term_graph.py` | Построение/анализ термин-графа для улучшения тематической релевантности контекста. |

## 5) Данные и инфраструктура, поддерживающие pipeline

| Файл | Функциональное назначение |
|---|---|
| `apps/api/logging_setup.py` | Настройка логирования этапов pipeline (upload/index/search/chat) для диагностики. |
| `scripts/verify.sh` | Сквозной backend smoke/e2e-скрипт: компиляция, тесты, запуск API, upload/index/chat-проверки. |
| `Makefile` | Быстрые команды запуска и проверки (`run-api`, `verify`, `smoke`) полного RAG-контура. |
| `apps/api/requirements.txt` | Python-зависимости, необходимые для работы FastAPI API и связанных RAG-сервисов. |

---

## 6) Второй слой: файл → ключевые функции/классы

### Upload и управление источниками

| Файл | Ключевые функции/классы |
|---|---|
| `apps/api/routers/sources.py` | `_save_multipart_file_stream` (чтение multipart upload), `_persist_content` (сохранение файла), `upload_source`, `add_path`, `reparse_source`, `delete_source`, `erase_source`, `delete_all_files`. |
| `apps/api/store.py` | `InMemoryStore` (центральный класс), методы `create_notebook`, `add_source`, `add_source_from_path`, `mark_source_indexing`, `mark_source_indexed`, `mark_source_failed`, `list_sources`, `delete_source`. |
| `apps/api/routers/notebooks.py` | CRUD-эндпоинты notebook-уровня (`create/list/get/delete`) и связанный lifecycle notebook. |

### Parsing

| Файл | Ключевые функции/классы |
|---|---|
| `apps/api/services/parse_service.py` | `DocumentParser` (основной парсер), `ParserConfig`, `ParsedChunk`, `DocumentMetadata`, `extract_blocks` (внешняя точка извлечения блоков), `_token_count`, `_sort_pdf_lines_multicolumn`. |
| `packages/rag_core/parsers/text_extraction.py` | `extract_blocks` (ядро извлечения), `_extract_pdf_pages`, `_extract_docx`, `_extract_txt`, `_split_sections`, `semantic_chunk`, `TextBlock`. |
| `packages/rag_core/parsers/preprocessing.py` | Функции очистки/нормализации текста перед chunking и retrieval. |
| `packages/rag_core/parsers/ner_extraction.py` | Функции извлечения именованных сущностей (NER) для enrichment индекса/контекста. |

### Chunking, embedding, vector DB / indexing

| Файл | Ключевые функции/классы |
|---|---|
| `apps/api/services/index_service.py` | `index_source` (основной индексатор source), `get_notebook_blocks`, `remove_source_blocks`, `clear_notebook_blocks`. |
| `apps/api/services/embedding_service.py` | `EmbeddingEngine` (построение векторных представлений/поиск), `EmbeddingClient`, `EmbeddedChunk`, `IndexMeta`, `SearchResult`, `_normalize`, `_matches_filters`, `_embedded_to_dict`. |
| `packages/rag_core/app/chunk_manager.py` | `semantic_chunking` (разбиение блоков в чанки), `_split_technical_sections`, `_chunk_text_with_overlap`, `get_sqlite_collection`, `ChunkStore`, `save_chunks_for_folder`, `add_chunk_to_folder`, `update_chunk_by_number`, `delete_chunk_by_number`. |
| `packages/rag_core/app/chunk_editor.py` | Вспомогательные функции редактирования/пересохранения chunk-коллекций и метаданных. |
| `packages/rag_core/app/engine.py` | `trigger_indexing` (extract→chunk→embed→save), `_get_embed_model`, `check_indexed_files`, `rebuild_index_from_folders`, `delete_index`. |

### Search, answer preparation и SSE streaming

| Файл | Ключевые функции/классы |
|---|---|
| `apps/api/services/search_service.py` | `search` (retrieval по notebook-индексу), `_query_to_groups`, `chunk_to_citation_fields`. |
| `apps/api/routers/chat.py` | `chat` (синхронный ответ), `chat_stream` (SSE-стрим), `to_sse`, `_to_citation`, `list_messages`, `clear_messages`. |
| `apps/api/services/model_chat.py` | `generate_model_answer`, `stream_model_answer`, `build_chat_history`, `_normalize_provider`. |
| `apps/api/services/chat_modes.py` | `normalize_chat_mode`, `build_answer`, `ChatModeSpec`. |
| `packages/rag_core/app/search_engine.py` | `run_fast_search`, `llm_generate_query`, `llm_summarize_chunks`, `_expand_query_groups`, `_group_match`. |
| `packages/rag_core/app/async_search.py` | `RemoteLibraryAsync`, `aggregated_search` (асинхронная агрегация retrieval-результатов). |
| `packages/rag_core/app/llm_generic.py` | `ask_llm`, `warmup_model`, `_iter_llama_cpp_stream`, `_iter_ollama_stream`, `_detect_backend`. |

### Поддержка и диагностика

| Файл | Ключевые функции/классы |
|---|---|
| `apps/api/main.py` | `on_startup` (инициализация логирования), `http_logging_middleware`, `health`/`root`. |
| `apps/api/logging_setup.py` | `setup_logging` и функции форматирования/настройки лог-хендлеров backend. |
| `scripts/verify.sh` | Bash-этапы `compileall`, `pytest`, smoke upload/index/chat c API-проверками. |

