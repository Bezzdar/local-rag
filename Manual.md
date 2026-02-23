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

> **Примечание для разработчика:** Фронтенд использует Next.js App Router. Все страницы в `app/` — серверные компоненты по умолчанию, но все они помечены `'use client'`, так как используют React-хуки. Управление состоянием реализовано без сторонних библиотек (Redux/Zustand) через `useSyncExternalStore` + модульные сторы.

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

### 4.3 Корневые файлы маршрутизации

#### `app/layout.tsx` — Корневой Layout

Оборачивает всё приложение в два провайдера:
- `<Providers>` — TanStack Query `QueryClientProvider` (из `components/providers.tsx`).
- `<StoreInitializer>` — клиентский компонент, вызывающий `initializeModeStore()`, `initializeConnectionStore()`, `initializeAgentStore()` при монтировании (из `components/StoreInitializer.tsx`).

#### `app/page.tsx` — Корневой маршрут

Простой серверный компонент: немедленно делает `redirect('/notebooks')`. Пользователь всегда попадает на страницу ноутбуков.

---

### 4.4 Главное меню ноутбуков

**Файл:** `apps/web/app/notebooks/page.tsx`

Страница со списком ноутбуков — первый экран, который видит пользователь.

#### Структура страницы

```
┌─────────────────────────────────────────────────────────────────┐
│  [h1: Notebooks]  [ConnectionIndicator]      [Новый ноутбук ▶]  │
├──────────────────────────────────┬──────────────────────────────┤
│  Список ноутбуков:               │  Правая панель настроек:     │
│  ┌──────────────────────────┐    │  [→/← свернуть]              │
│  │ Название ноутбука        │    │  ┌──────────────────────┐    │
│  │ Дата обновления          │    │  │ [−] Провайдер LLM    │    │
│  │ [Переименовать] [Дубл.]  │    │  │   <RuntimeSettings>  │    │
│  │ [Удалить]                │    │  ├──────────────────────┤    │
│  └──────────────────────────┘    │  │ [−] Глоб. парсинг   │    │
│  ...                             │  │   <ParsingSettings>  │    │
│                                  │  └──────────────────────┘    │
└──────────────────────────────────┴──────────────────────────────┘
```

#### Состояние компонента (useState)

| Переменная | Тип | Назначение |
|---|---|---|
| `isSettingsOpen` | `boolean` | Свёрнута/раскрыта правая боковая панель настроек |
| `isRuntimeOpen` | `boolean` | Свёрнут/раскрыт блок «Провайдер LLM» |
| `isParsingOpen` | `boolean` | Свёрнут/раскрыт блок «Глобальные настройки парсинга» |
| `selectedNotebookId` | `string\|null` | Активный ноутбук для настроек парсинга |
| `isDialogOpen` | `boolean` | Открыт диалог создания ноутбука |
| `newNotebookName` | `string` | Текущее имя в поле ввода создания |
| `isRenameDialogOpen` | `boolean` | Открыт диалог переименования |
| `renamingNotebookId` | `string\|null` | ID ноутбука, который переименовывается |
| `renameNotebookName` | `string` | Текущее имя в поле ввода переименования |

#### TanStack Query (данные и мутации)

| Хук | Key | Действие |
|---|---|---|
| `useQuery` | `['notebooks']` | Загружает список ноутбуков: `api.listNotebooks()` |
| `useMutation` | `createNotebook` | `api.createNotebook(title)` → инвалидирует `['notebooks']` |
| `useMutation` | `deleteNotebook` | `api.deleteNotebook(id)` → инвалидирует `['notebooks']` |
| `useMutation` | `renameNotebook` | `api.renameNotebook(id, title)` → инвалидирует `['notebooks']` |
| `useMutation` | `duplicateNotebook` | `api.duplicateNotebook(id)` → инвалидирует `['notebooks']` |

#### UI-элементы и их функции

| Элемент | Обработчик / Функция | Описание |
|---|---|---|
| `[Новый ноутбук]` | `openDialog()` | Логирует `ui.notebook.create_dialog_open`, открывает модальный диалог |
| Список ноутбуков | `onClick` → `setSelectedNotebookId` | Выделяет ноутбук для настроек парсинга |
| `<Link href="/notebooks/{id}">` | — | Переход в рабочее окно ноутбука, логирует `ui.notebook.opened` |
| `[Переименовать]` | `openRenameDialog(id, title)` | Открывает модальный диалог переименования |
| `[Дублировать]` | `duplicateNotebook.mutate(id)` | Вызывает API дублирования |
| `[Удалить]` | `deleteNotebook.mutate(id)` | Вызывает API удаления без подтверждения (прямой вызов) |
| `[→/←]` (кнопка панели) | `setIsSettingsOpen(toggle)` | Сворачивает/разворачивает правую панель настроек |
| `[−/+] Провайдер LLM` | `setIsRuntimeOpen(toggle)` | Сворачивает/разворачивает блок LLM-настроек |
| `[−/+] Глобальные настройки парсинга` | `setIsParsingOpen(toggle)` | Сворачивает/разворачивает блок настроек парсинга |

#### Модальные диалоги

**Диалог создания ноутбука** (`isDialogOpen`):
- Поле ввода имени (`newNotebookName`).
- `Enter` → `handleCreate()`: формирует имя (или timestamp), вызывает `createNotebook.mutate(title)`, закрывает диалог.
- `Escape` / `[Отмена]` → `handleCancel()`.

**Диалог переименования** (`isRenameDialogOpen`):
- Поле ввода нового имени (`renameNotebookName`).
- `Enter` / `[Переименовать]` → `handleRename()`: вызывает `renameNotebook.mutate({id, title})`.
- `Escape` / `[Отмена]` → `handleRenameCancel()`.

#### Правая панель настроек (on главном меню)

Панель с двумя секциями, sticky — прокрутка не скрывает её:
1. **«Провайдер LLM»** — рендерит `<RuntimeSettings />` (см. раздел 4.8).
2. **«Глобальные настройки парсинга»** — рендерит `<ParsingSettingsPanel notebookId={activeNotebookId} />` (см. раздел 4.9).

Кнопка `[→]`/`[←]` сворачивает всю панель до 48px, скрывая содержимое.

---

### 4.5 Рабочее окно ноутбука

**Файл:** `apps/web/app/notebooks/[id]/page.tsx`

Основной экран работы с ноутбуком. Рендерится по маршруту `/notebooks/{notebookId}`.

#### Структура страницы (три зоны)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [ConnectionIndicator]                                                    │
├──────────────────┬─┬───────────────────────────────────┬─┬─────────────┤
│ ЛЕВАЯ ПАНЕЛЬ     │▌│         ЦЕНТРАЛЬНАЯ ПАНЕЛЬ         │▌│ ПРАВАЯ      │
│ (SourcesPanel)   │ │         (ChatPanel)                │ │ ПАНЕЛЬ      │
│                  │R│                                    │R│ (EvidenceP) │
│ [⟨/⟩]           │e│                                    │e│ [⟩/⟨]      │
│ Список ноутбуков │s│ [Chat]    [Очистить] [Режим▾]      │s│ [Цитаты]   │
│ (select)         │i│ ─────────────────────────────────  │i│ [Заметки]  │
│ Поиск источников │z│ История сообщений                  │z│            │
│ Upload файла     │e│ Стриминг ответа                    │e│ Сохранённые│
│ Кнопки действий  │ │ ─────────────────────────────────  │ │ цитаты     │
│ Список файлов    │L│ [Ввод вопроса...] [Отправить]      │R│ Глобальные │
│                  │ │                                    │ │ заметки    │
└──────────────────┴─┴───────────────────────────────────┴─┴─────────────┘
```

Разделители `▌` — перетаскиваемые (drag-to-resize), реализованы через `startResize('left'|'right')`.

#### Границы размеров панелей

```typescript
const LEFT_MIN = 240;   // px, минимум левой панели
const LEFT_MAX = 520;   // px, максимум левой панели
const RIGHT_MIN = 280;  // px, минимум правой панели
const RIGHT_MAX = 640;  // px, максимум правой панели
```

#### Состояние компонента (useState)

| Переменная | Тип | Назначение |
|---|---|---|
| `streaming` | `string` | Накапливающийся текст текущего стрима |
| `citations` | `Citation[]` | Цитаты текущего ответа (обновляются по событию `citations` SSE) |
| `explicitSelection` | `string[]\|null` | Явно выбранные источники (null = все enabled) |
| `leftWidth` | `number` | Ширина левой панели в px (default 320) |
| `rightWidth` | `number` | Ширина правой панели в px (default 360) |
| `leftCollapsed` | `boolean` | Свёрнута левая панель (44px) |
| `rightCollapsed` | `boolean` | Свёрнута правая панель (44px) |
| `sourceConfigModal` | `SourceConfigModalState\|null` | Открыт модал настройки парсинга источника |

#### Сторы, используемые страницей

| Стор | Что берётся |
|---|---|
| `useModeStore()` | `currentMode` — текущий режим чата |
| `useAgentStore()` | `selectedAgentId` — выбранный агент |
| `useChatStore()` | `isClearing` — активна ли очистка чата |

#### TanStack Query (данные и мутации)

| Хук | Key | Действие |
|---|---|---|
| `useQuery` | `['notebooks']` | Список ноутбуков (для select в SourcesPanel) |
| `useQuery` | `['agents']` | Список агентов (для select в ChatPanel) |
| `useQuery` | `['sources', notebookId]` | Источники текущего ноутбука |
| `useQuery` | `['messages', notebookId]` | История чата |
| `useQuery` | `['notes', notebookId]` | Заметки ноутбука |
| `useQuery` | `['parsing-settings', notebookId]` | Настройки парсинга (для модала источника) |
| `useQuery` | `['saved-citations', notebookId]` | Сохранённые цитаты |
| `useQuery` | `['global-notes']` | Глобальные заметки (cross-notebook) |
| `useMutation` | `uploadSource` | Загрузка файла через multipart/form-data |
| `useMutation` | `deleteSources` | Удаление массива источников |
| `useMutation` | `eraseSource` | Стирание parsing/DB данных источника (файл сохраняется) |
| `useMutation` | `reparseSource` | Перезапуск индексации источника |
| `useMutation` | `updateSource` | Обновление `is_enabled` или `individual_config` источника |
| `useMutation` | `openSource` | Открыть файл системным приложением (через ОС) |
| `useMutation` | `reorderSources` | Сохранить новый порядок источников (drag-and-drop) |
| `useMutation` | `createNote` | Создать заметку в ноутбуке |
| `useMutation` | `saveCitation` | Сохранить цитату (клик по [N] в чате) |
| `useMutation` | `deleteSavedCitation` | Удалить сохранённую цитату |
| `useMutation` | `saveGlobalNote` | Сохранить глобальную заметку (кнопка ↳) |
| `useMutation` | `deleteGlobalNote` | Удалить глобальную заметку |
| `useMutation` | `clearChat` | Очистить историю чата |

#### Ключевые функции страницы

**`sendMessage(text: string)`** — отправка сообщения в чат:
1. Логирует событие `ui.message.send_attempt`.
2. Прерывает предыдущий поток (если был) через `closeStreamRef.current?.()`.
3. Сбрасывает `streaming` и `citations`.
4. Строит идентификатор потока `streamId = {notebookId}-{timestamp}`.
5. Определяет режим `streamMode` из `currentMode`.
6. Получает `runtimeConfig` (провайдер, модель, base_url, maxHistory).
7. Вызывает `openChatStream(...)` из `lib/sse.ts`.
8. Сохраняет функцию закрытия потока в `closeStreamRef.current`.

**`handleToggleSource(sourceId)`** — включение/выключение источника в чате:
- Управляет `explicitSelection` (null → все, [] → никто, [ids...] → выборочно).

**`handleDeleteSources(sourceIds, confirmText)`** — удаление источников:
- Вызывает `window.confirm(confirmText)` для подтверждения.
- После успеха — убирает удалённые ID из `explicitSelection`.

**`startResize(side: 'left'|'right')`** — drag-to-resize панелей:
- Добавляет глобальные обработчики `mousemove`/`mouseup`.
- Обновляет `leftWidth`/`rightWidth` с учётом MIN/MAX ограничений.
- При движении — автоматически разворачивает свёрнутую панель.

#### Модал настройки парсинга источника

Открывается кнопкой `⚙` в строке источника. Содержит поля в зависимости от метода чанкинга:

| Метод | Поля |
|---|---|
| `general` | chunk_size, chunk_overlap |
| `context_enrichment` | chunk_size, chunk_overlap, context_window, use_llm_summary |
| `hierarchy` | doc_type, chunk_size (fallback) |
| `pcr` | parent_chunk_size, child_chunk_size |
| `symbol` | symbol_separator |
| Все методы | ocr_enabled, ocr_language |

Каждый параметр имеет чекбокс «Глобальный» — если включён, поле отключено и используется значение из глобальных настроек парсинга.

При сохранении вызывает `updateSource.mutate({sourceId, payload: {individual_config: {...}}})`.

---
