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
| `apps/api/config.py` | Пути к `data/docs`, `data/chunks`, `data/index` и другие backend-настройки, влияющие на pipeline. |

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

## Дополнение

Если нужно, могу в следующем шаге добавить в этот документ второй слой: **"файл → ключевые функции/классы"** (например, какие конкретно функции отвечают за upload, parsing, chunking, indexing, search и SSE-streaming).
