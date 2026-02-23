# Manual — Local RAG Assistant

## 1. Назначение документа

Этот документ — основной технический справочник проекта **Local RAG Assistant** для разработчиков, QA-инженеров, DevOps и ИИ-агентов.

Документ содержит:
- описание структуры репозитория и назначение каждого файла;
- детальное описание UI-элементов фронтенда (с указанием файлов и функций);
- описание бэкенд-логики (функции, порядок обработки, API-контракты);
- схемы ключевых потоков данных;
- правила работы с проектом.

---

## 2. Краткое описание продукта

**Local RAG Assistant** — локальный NotebookLM-подобный ассистент. Пользователь создаёт «ноутбуки», загружает в них документы (PDF, DOCX, XLSX, TXT и др.), система индексирует содержимое и отвечает на вопросы с цитированием источников.

Ключевые свойства:
- Работает полностью локально (подходит для закрытых корпоративных контуров).
- LLM и embedding-модели подключаются через Ollama или OpenAI-compatible API.
- Поиск — гибридный: векторный (cosine similarity) + полнотекстовый (FTS5/BM25), объединяются через RRF.
- Ответы потоковые (SSE).

---

## 3. Структура репозитория

```
RAG/
├── apps/
│   ├── api/                    # Бэкенд (FastAPI, Python)
│   └── web/                    # Фронтенд (Next.js, TypeScript)
├── agent/
│   ├── agent_001/              # Агент-001: базовая реализация агента
│   └── agent_002/              # Агент-002: manifest только
├── data/                       # Данные приложения (создаётся при первом запуске)
│   ├── docs/                   # Загруженные документы (по notebook_id)
│   ├── parsing/                # JSON-чанки после парсинга (по notebook_id)
│   ├── notebooks/              # SQLite БД на каждый ноутбук (поиск)
│   ├── citations/              # Сохранённые цитаты (JSON, по notebook_id)
│   ├── notes/                  # Глобальные заметки (JSON)
│   ├── logs/sessions/          # Логи сессий (app_*.log, ui_*.log)
│   └── store.db                # Глобальная SQLite БД (ноутбуки, источники, настройки парсинга)
├── packages/                   # Пустой пакет-заглушка
├── scripts/
│   ├── dev_run.sh              # Скрипт запуска для Linux/macOS
│   ├── verify.sh               # Скрипт проверки окружения
│   └── cleanup_data.ps1        # PowerShell: очистка данных
├── .env.example                # Пример переменных окружения
├── .gitignore
├── launch.bat                  # Интерактивный Windows-лаунчер
├── Makefile                    # make dev / make install / make test
├── Manual.md                   # Этот документ
├── README.md                   # Пользовательский README с инструкцией по запуску
└── requirements.txt            # Корневые зависимости (объединяет api + web)
```

### 3.1 Директория `data/` — хранение данных

| Поддиректория / файл | Назначение |
|---|---|
| `data/store.db` | Глобальная SQLite БД: таблицы `notebooks`, `sources`, `parsing_settings`. Персистентна между перезапусками. |
| `data/docs/{notebook_id}/` | Физические файлы документов, загруженных в ноутбук. |
| `data/parsing/{notebook_id}/{source_id}.json` | Результат парсинга: список чанков с метаданными (JSON-массив). |
| `data/notebooks/{notebook_id}.db` | SQLite БД ноутбука: таблицы `documents`, `chunks`, `chunks_fts`, `chunk_embeddings`, `tags`, `document_tags`. Используется для векторного и полнотекстового поиска. |
| `data/citations/{notebook_id}/{citation_id}.json` | Сохранённые пользователем цитаты (кнопка [N] в чате). |
| `data/notes/{note_id}.json` | Глобальные заметки (кнопка ↳ в чате), доступны из любого ноутбука. |
| `data/logs/sessions/` | Логи сессии: `app_<SESSION_ID>.log` — сервер, `ui_<SESSION_ID>.log` — UI-события. |

---

## 4. Frontend (`apps/web`)

### 4.1 Технологический стек

| Технология | Версия/назначение |
|---|---|
| Next.js (App Router) | SSR/CSR фреймворк |
| TypeScript | Типизация |
| TailwindCSS | Стилизация |
| TanStack Query (react-query) | Server state management (запросы к API, кэш, мутации) |
| Zod | Валидация ответов API |
| EventSource (native) | SSE-стриминг чата |
| `useSyncExternalStore` | Клиентские сторы (не Zustand/Redux — ручная реализация) |

### 4.2 Структура файлов фронтенда

```
apps/web/
├── app/
│   ├── globals.css             # Глобальные стили
│   ├── layout.tsx              # Корневой layout (обёртка Providers + StoreInitializer)
│   ├── page.tsx                # Корневой маршрут (redirect на /notebooks)
│   └── notebooks/
│       ├── page.tsx            # ГЛАВНОЕ МЕНЮ: список ноутбуков
│       └── [id]/
│           └── page.tsx        # РАБОЧЕЕ ОКНО: левая + центр + правая панели
├── components/
│   ├── SourcesPanel.tsx        # ЛЕВОЕ ВЫДВИЖНОЕ МЕНЮ: список источников
│   ├── ChatPanel.tsx           # ЦЕНТРАЛЬНАЯ ПАНЕЛЬ: чат
│   ├── EvidencePanel.tsx       # ПРАВОЕ ВЫДВИЖНОЕ МЕНЮ: цитаты и заметки
│   ├── RuntimeSettings.tsx     # БЛОК НАСТРОЕК ПРОВАЙДЕРА LLM
│   ├── ParsingSettingsPanel.tsx# Блок глобальных настроек парсинга
│   ├── ConnectionIndicator.tsx # Индикатор подключения LLM
│   ├── providers.tsx           # TanStack Query провайдер
│   └── StoreInitializer.tsx    # Клиентская инициализация сторов
├── lib/
│   ├── api.ts                  # HTTP-клиент (все REST-вызовы к бэкенду)
│   ├── sse.ts                  # SSE-клиент для стриминга чата
│   ├── runtime-config.ts       # Конфигурация LLM-провайдера (localStorage)
│   └── clientLogger.ts         # Логгер UI-событий (POST /api/client-events)
├── src/stores/
│   ├── chatStore.ts            # Стор: состояние очистки чата, поток
│   ├── modeStore.ts            # Стор: текущий режим чата (rag/model/agent)
│   ├── connectionStore.ts      # Стор: состояние подключения LLM
│   └── agentStore.ts           # Стор: выбранный агент
├── types/
│   └── dto.ts                  # TypeScript-типы и Zod-схемы DTO
├── e2e/
│   └── notebook-chat.spec.ts   # Playwright e2e тесты
├── next.config.mjs             # Next.js конфигурация
├── tailwind.config.ts          # Tailwind конфигурация
├── tsconfig.json               # TypeScript конфигурация
└── package.json                # Зависимости фронтенда
```

---
