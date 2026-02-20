# REVISION — инвентаризация backend-файлов

Ниже приведён список backend-файлов с путями **относительно корня проекта** и кратким функциональным назначением.

## `apps/api` (активный FastAPI backend)

| Файл | Назначение |
|---|---|
| `apps/api/__init__.py` | Инициализация Python-пакета backend API. |
| `apps/api/main.py` | Точка входа FastAPI-приложения: создание app, подключение роутеров, health-check endpoints, middleware. |
| `apps/api/config.py` | Конфигурация backend: пути к данным, лимиты и системные настройки API. |
| `apps/api/schemas.py` | Pydantic-схемы (DTO) для запросов/ответов API. |
| `apps/api/store.py` | In-memory хранилище состояния и orchestration жизненного цикла notebooks/sources/messages/notes и индексации. |
| `apps/api/logging_setup.py` | Конфигурация и инициализация логирования backend-сервисов. |
| `apps/api/requirements.txt` | Python-зависимости backend API. |
| `apps/api/routers/__init__.py` | Инициализация пакета роутеров FastAPI. |
| `apps/api/routers/chat.py` | HTTP/SSE-эндпоинты для чата и стриминга ответов. |
| `apps/api/routers/client_events.py` | Эндпоинты приёма клиентских событий/телеметрии. |
| `apps/api/routers/notebooks.py` | CRUD-операции и сервисные endpoints для notebooks. |
| `apps/api/routers/llm.py` | Эндпоинты, связанные с LLM-настройками/вызовами. |
| `apps/api/routers/notes.py` | Эндпоинты управления заметками пользователя. |
| `apps/api/routers/sources.py` | Эндпоинты загрузки, удаления и индексации источников документов. |
| `apps/api/services/__init__.py` | Инициализация пакета backend-сервисов. |
| `apps/api/services/chat_modes.py` | Логика режимов чата и выбора сценария ответа. |
| `apps/api/services/model_chat.py` | Сервис взаимодействия с LLM-моделью/генератором ответов. |
| `apps/api/services/search_service.py` | Retrieval-поиск по индексированным чанкам и формирование citation-данных. |
| `apps/api/services/index_service.py` | Конвейер индексации: преобразование parser-блоков в индексируемую структуру. |
| `apps/api/services/embedding_service.py` | Подготовка/получение эмбеддингов (или их имитации) для поиска. |
| `apps/api/services/parse_service.py` | Парсинг загруженных документов и нормализация текстовых блоков. |
| `apps/api/tests/conftest.py` | Общие pytest-фикстуры и подготовка тестового окружения backend. |
| `apps/api/tests/test_health_endpoints.py` | Тесты health-check endpoints backend API. |
| `apps/api/tests/test_llm_router.py` | Тесты роутера LLM и связанных контрактов API. |
| `apps/api/tests/test_sources_lifecycle.py` | Тесты полного жизненного цикла источников (upload/index/delete). |
| `apps/api/tests/test_upload_and_stream.py` | Тесты загрузки файлов и SSE-стриминга ответов. |
| `apps/api/tests/test_embedding_service.py` | Тесты сервиса эмбеддингов. |
| `apps/api/tests/test_parsing_settings.py` | Тесты API/логики настроек парсинга. |
| `apps/api/tests/test_document_parser/test_document_parser.py` | Тесты парсинга документов по форматам и сценариям извлечения текста. |

## `packages/rag_core` (библиотечное backend-ядро и legacy-компоненты)

| Файл | Назначение |
|---|---|
| `packages/rag_core/__init__.py` | Инициализация пакета `rag_core`. |
| `packages/rag_core/app/__init__.py` | Инициализация подпакета прикладной логики legacy-ядра. |
| `packages/rag_core/app/config.py` | Конфигурация параметров ядра RAG (индексация, поиск, runtime-настройки). |
| `packages/rag_core/app/engine.py` | Основной orchestrator legacy RAG-пайплайна (extract → chunk → index/search). |
| `packages/rag_core/app/chunk_manager.py` | Семантический/структурный чанкинг текста (включая parent/child-структуры). |
| `packages/rag_core/app/chunk_editor.py` | Утилиты редактирования/постобработки чанков. |
| `packages/rag_core/app/search_engine.py` | Поисковый движок (retrieval/ranking) для ядра RAG. |
| `packages/rag_core/app/search_tools.py` | Вспомогательные функции и инструменты для поиска и ранжирования. |
| `packages/rag_core/app/llm_generic.py` | Унифицированный интерфейс обращения к LLM в legacy-контуре. |
| `packages/rag_core/app/async_search.py` | Асинхронные сценарии выполнения retrieval-поиска. |
| `packages/rag_core/app/math_engine.py` | Математические/оценочные операции, используемые в retrieval-логике. |
| `packages/rag_core/app/term_graph.py` | Построение и анализ графа терминов/связей в текстовом корпусе. |
| `packages/rag_core/app/user_settings.py` | Работа с пользовательскими настройками ядра RAG. |
| `packages/rag_core/app/user_settings.json` | Значения настроек ядра по умолчанию/профиль пользователя. |
| `packages/rag_core/parsers/__init__.py` | Инициализация пакета парсеров. |
| `packages/rag_core/parsers/text_extraction.py` | Извлечение текста из файлов (PDF/DOCX/TXT и др.), очистка, секционирование. |
| `packages/rag_core/parsers/preprocessing.py` | Предобработка текста перед чанкингом и индексированием. |
| `packages/rag_core/parsers/ner_extraction.py` | Извлечение сущностей (NER) для enrichment/аналитики текста. |

## Инфраструктурные backend-скрипты

| Файл | Назначение |
|---|---|
| `scripts/dev_run.sh` | Локальный запуск backend/frontend в dev-режиме. |
| `scripts/verify.sh` | Скрипт проверки backend-контура (pytest/smoke/e2e API-проверки). |
| `Makefile` | Команды-обёртки для запуска и проверки backend (например, `run-api`, `verify`, `smoke`). |
