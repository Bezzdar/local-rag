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

### 4.6 Левое выдвижное меню — Sources Panel

**Файл:** `apps/web/components/SourcesPanel.tsx`

Панель управления источниками ноутбука. Рендерится внутри `app/notebooks/[id]/page.tsx` при `!leftCollapsed`.

#### Структура UI (сверху вниз)

```
┌─────────────────────────────────────────────┐
│ Notebooks                                    │
│ [select: Выбор ноутбука ▾]                  │
├─────────────────────────────────────────────┤
│ [На главную страницу]                        │
├─────────────────────────────────────────────┤
│ [Search sources]                             │
│ [Upload PDF/DOCX/XLSX]  (file input)         │
├─────────────────────────────────────────────┤
│ [Выделить все]  [Снять выделение]            │
│ [Парсить все]   [Парсить выбранное]          │
│ [Удалить выбранное] [Удалить невыбранные]    │
├─────────────────────────────────────────────┤
│ Список источников (scrollable, max 55vh):    │
│ ┌──────────────────────────────────────────┐│
│ │ [#] ☑ filename.pdf   [indexed] d p b     ││
│ │                      [▶] [⚙] [✖] [🗑]    ││
│ └──────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

#### Props компонента

| Prop | Тип | Описание |
|---|---|---|
| `notebooks` | `Notebook[]` | Все ноутбуки (для select) |
| `activeNotebookId` | `string` | ID текущего ноутбука |
| `sources` | `Source[]` | Источники текущего ноутбука |
| `selectedSourceIds` | `string[]` | ID включённых источников для чата |
| `onNotebookChange` | `(id) => void` | Переход в другой ноутбук |
| `onToggleSource` | `(sourceId) => void` | Вкл/выкл источника для чата |
| `onSelectAllSources` | `() => void` | Выбрать все |
| `onClearSourceSelection` | `() => void` | Снять выделение |
| `onDeleteSelectedSources` | `() => void` | Удалить выбранные |
| `onDeleteUnselectedSources` | `() => void` | Удалить невыбранные |
| `onParseAllSources` | `() => void` | Запустить парсинг всех |
| `onParseSelectedSources` | `() => void` | Запустить парсинг выбранных |
| `onUpload` | `(file) => void` | Загрузить файл |
| `onEraseSource` | `(source) => void` | Стереть данные парсинга (не файл) |
| `onOpenConfig` | `(source) => void` | Открыть модал настройки парсинга |
| `onDeleteSource` | `(source) => void` | Удалить источник полностью |
| `onParseSource` | `(source) => void` | Запустить парсинг одного источника |
| `onOpenSource` | `(source) => void` | Открыть файл в ОС-приложении |
| `onReorderSources` | `(orderedIds) => void` | Сохранить новый порядок после drag-and-drop |

#### Внутреннее состояние компонента

| Переменная | Тип | Назначение |
|---|---|---|
| `search` | `string` | Фильтр поиска по имени файла |
| `dragOverId` | `string\|null` | ID строки-цели при drag-and-drop |
| `dragSourceId` | `ref<string\|null>` | ID перетаскиваемого источника |

#### Сортировка и фильтрация

- `sortedSources` — источники сортируются по `sort_order` (ASC), затем по `added_at`.
- `docNumbers` — словарь `{source_id: N}` (1-based, по позиции в `sortedSources`). Отображается в бейдже слева.
- `visibleSources` — фильтр по `search` (case-insensitive по `filename`).

#### Drag-and-drop

Реализован через HTML5 Drag API:

| Обработчик | Действие |
|---|---|
| `handleDragStart(e, sourceId)` | Запоминает `dragSourceId.current = sourceId`, устанавливает `effectAllowed = 'move'` |
| `handleDragOver(e, targetId)` | `e.preventDefault()`, устанавливает `dragOverId = targetId` (визуальный highlight) |
| `handleDrop(e, targetId)` | Строит новый порядок: вырезает `fromId` из массива, вставляет на позицию `targetId`, вызывает `onReorderSources(newOrder)` |
| `handleDragEnd()` | Сбрасывает `dragOverId` и `dragSourceId.current` |

#### Элементы строки источника

| Элемент | Описание |
|---|---|
| `[#]` | Бейдж с порядковым номером документа в ноутбуке (1-based, фиксированный, определяет [N] в цитатах) |
| `☑` (checkbox) | Вкл/выкл источника для включения в контекст чата → `onToggleSource` |
| `filename` | Имя файла (truncate при переполнении). Двойной клик → `onOpenSource` |
| `[status]` | Бейдж статуса: `new` / `indexing` / `indexed` / `failed` |
| `d p b` | Индикаторы-лампочки (компонент `Lamp`): **d** — `has_docs`, **p** — `has_parsing`, **b** — `has_base` |
| `[▶]` | Кнопка ручного запуска парсинга → `onParseSource` |
| `[⚙]` | Кнопка настройки парсинга файла → `onOpenConfig` (открывает модал в родительском компоненте) |
| `[✖]` | Стереть parsing/base данные, файл сохраняется → `onEraseSource` (с `window.confirm`) |
| `[🗑]` | Удалить источник полностью (файл + данные + DB) → `onDeleteSource` |

#### Загрузка файла

Реализована через скрытый `<input type="file">`, обёрнутый в `<label>`. При выборе файла вызывает `onUpload(file)`. Поддерживаемые форматы не ограничены на уровне UI (фильтрация на бэкенде).

---

### 4.7 Центральная панель чата

**Файл:** `apps/web/components/ChatPanel.tsx`

#### Структура UI

```
┌───────────────────────────────────────────────────────────┐
│ [h2: Chat]         [Очистить чат] [Агент▾] [Режим▾]       │
├───────────────────────────────────────────────────────────┤
│ Область сообщений (flex-1, min-h-40vh, overflow-auto):    │
│                                                            │
│  [user]  Вопрос пользователя                              │
│  [assistant] Ответ с [1][2] ссылками        [↳]           │
│  ...                                                       │
│  [Текущий стрим, если есть]                               │
├───────────────────────────────────────────────────────────┤
│ [Введите вопрос...]                   [Отправить]         │
├───────────────────────────────────────────────────────────┤
│ (если стрим активен): [Copy] [Сохранить в Заметки]        │
│                        Источников: N                       │
└───────────────────────────────────────────────────────────┘
```

#### Props

| Prop | Тип | Описание |
|---|---|---|
| `notebookId` | `string` | ID ноутбука |
| `mode` | `ChatMode` | Текущий режим: `'rag' \| 'model' \| 'agent'` |
| `agentId` | `string` | ID выбранного агента |
| `agents` | `AgentManifest[]` | Список агентов (для select, виден только в режиме `agent`) |
| `messages` | `ChatMessage[]` | История сообщений |
| `streaming` | `string` | Текст текущего стрима |
| `citations` | `Citation[]` | Цитаты текущего ответа |
| `disableSend` | `boolean` | Блокировка отправки (при очистке чата) |
| `disableClearChat` | `boolean` | Блокировка очистки |
| `onModeChange` | `(mode) => void` | Смена режима |
| `onAgentChange` | `(agentId) => void` | Смена агента |
| `onSend` | `(text) => void` | Отправка сообщения |
| `onClearChat` | `() => void` | Очистка чата |
| `onSaveToNotes` | `(text) => void` | Сохранить в заметки |
| `onCitationClick` | `(citation) => void` | Клик по номеру цитаты |

#### Внутреннее состояние

| Переменная | Тип | Назначение |
|---|---|---|
| `input` | `string` | Текущее содержимое поля ввода |

#### Отправка сообщения

- `Enter` (без Shift) → `onSend(input.trim())`, сброс поля.
- Кнопка `[Отправить]` → то же.
- `Shift+Enter` — вставляет перенос строки (стандартное поведение textarea).

#### Рендеринг цитат в тексте (`parseTextWithCitations` + `CitationRef`)

Функция `parseTextWithCitations(text)` разбирает текст ответа на сегменты:
- `{type: 'text', content: '...'}` — обычный текст.
- `{type: 'ref', num: N}` — ссылка `[N]`.

Компонент `CitationRef` для каждой ссылки:
- Ищет в `citations[]` цитату с `doc_order === N`.
- Если найдена — рендерит синюю кнопку `[N]`, при клике → `onCitationClick(citation)`.
- Если не найдена — рендерит серый текст `[N]`.

#### Режимы чата (select)

Опции из `CHAT_MODE_OPTIONS` (`lib/sse.ts`):
- `'rag'` — «RAG» (поиск только по загруженным источникам)
- `'model'` — «Модель» (аналитический режим, LLM с источниками)
- `'agent'` — «Агент» (заглушка)

При режиме `agent` и наличии агентов появляется второй select — выбор агента.

---

### 4.8 Правое выдвижное меню — Evidence Panel

**Файл:** `apps/web/components/EvidencePanel.tsx`

Правая панель для хранения и просмотра сохранённых цитат и глобальных заметок. Рендерится внутри `app/notebooks/[id]/page.tsx` при `!rightCollapsed`.

#### Структура UI

```
┌────────────────────────────────────┐
│ [Цитаты]  [Заметки]                │  ← табы
├────────────────────────────────────┤
│ Вкладка «Цитаты»:                  │
│ ┌──────────────────────────────┐   │
│ │ [N] filename.pdf · стр. X   [✕]  │
│ │ Текст фрагмента (chunk_text) │   │
│ │ Источник: Ноутбук · abc123…  │   │
│ │ [Показать документ]          │   │
│ └──────────────────────────────┘   │
│ ...                                │
├────────────────────────────────────┤
│ Вкладка «Заметки»:                 │
│ ┌──────────────────────────────┐   │
│ │ Ноутбук · 23.02.2026        [✕]  │
│ │ Текст заметки                │   │
│ └──────────────────────────────┘   │
└────────────────────────────────────┘
```

#### Props

| Prop | Тип | Описание |
|---|---|---|
| `savedCitations` | `SavedCitation[]` | Список сохранённых цитат ноутбука |
| `globalNotes` | `GlobalNote[]` | Список глобальных заметок (cross-notebook) |
| `sources` | `Source[]` | Источники (не используется напрямую, передаётся для расширяемости) |
| `onDeleteCitation` | `(citation) => void` | Удалить цитату → кнопка `[✕]` |
| `onDeleteNote` | `(note) => void` | Удалить заметку → кнопка `[✕]` |
| `onOpenSource` | `(sourceId) => void` | Открыть документ в ОС-приложении |

#### Внутреннее состояние

| Переменная | Тип | Назначение |
|---|---|---|
| `tab` | `'citations' \| 'notes'` | Активная вкладка (default: `'citations'`) |

#### Вкладка «Цитаты»

Отображает `savedCitations` (из `data/citations/{notebookId}/*.json`).

Для каждой цитаты:
- Бейдж `[N]` с `doc_order` — порядковый номер документа в ноутбуке.
- Имя файла + страница (`location.page`), если есть.
- Кнопка `[✕]` → `onDeleteCitation(citation)`.
- Текст фрагмента (`chunk_text`).
- Метка источника: `source_type` (`'notebook'` → «Ноутбук», иначе «БД») + первые 8 символов `source_notebook_id`.
- Кнопка `[Показать документ]` → `onOpenSource(citation.source_id)`.

Пустое состояние: подсказка «Нажмите на номер источника [N] в ответе чата, чтобы сохранить цитату».

#### Вкладка «Заметки»

Отображает `globalNotes` (из `data/notes/*.json`, общие для всех ноутбуков).

Для каждой заметки:
- Заголовок: `source_notebook_title` + дата создания.
- Кнопка `[✕]` → `onDeleteNote(note)`.
- Текст заметки (`content`).

Пустое состояние: подсказка «Нажмите ↳ под ответом чата, чтобы сохранить заметку».

#### Как наполняются цитаты и заметки

- **Цитата** добавляется через клик на синюю кнопку `[N]` в тексте ответа в `ChatPanel` → `onCitationClick` → `saveCitation.mutate(citation)` в родительской странице → API `POST /api/notebooks/{id}/saved-citations`.
- **Заметка** добавляется через кнопку `↳` под сообщением ассистента или через `[Сохранить в Заметки]` при активном стриме → `onSaveToNotes` → `saveGlobalNote.mutate(content)` → API `POST /api/notes`.

---

### 4.9 Блок настроек провайдера LLM — RuntimeSettings

**Файл:** `apps/web/components/RuntimeSettings.tsx`

Компонент настройки LLM-провайдера. Отображается в правой панели **главного меню** (`app/notebooks/page.tsx`) внутри секции «Провайдер LLM».

#### Структура UI

```
┌─────────────────────────────────────────────────────┐
│ Провайдер LLM                                       │
│ Текущий режим: None                                 │
├─────────────────────────────────────────────────────┤
│ Порт подключения: [http://localhost:11434] [Принять]│
├─────────────────────────────────────────────────────┤
│ [-] Настройки чата                                  │
│   Поставщик: [None / Ollama / OpenAI-compatible ▾] │
│   Модель чата: [select ▾]                           │
│   Лимит истории чата (1..50): [5]                  │
│   ☐ debug_model_mode                               │
│   [Подключить] [Сохранить] [Отключить]             │
├─────────────────────────────────────────────────────┤
│ [-] Эмбеддинг                                       │
│   Поставщик: [None / Ollama / OpenAI-compatible ▾] │
│   Модель эмбеддинга: [select ▾]                    │
│   [Сохранить]                                       │
└─────────────────────────────────────────────────────┘
```

#### Основное состояние компонента

| Переменная | Тип | Назначение |
|---|---|---|
| `runtime` | `RuntimeConfig` | Текущая применённая конфигурация (из `lib/runtime-config.ts`) |
| `draft` | `RuntimeDraft` | Черновик редактируемых настроек |
| `acceptedBase` | `string` | Принятый (применённый) base URL |
| `chatModels` | `string[]` | Список моделей чата, загруженных с Ollama |
| `embeddingModels` | `string[]` | Список embedding-моделей |
| `loadingChatModels` | `boolean` | Идёт загрузка списка chat-моделей |
| `loadingEmbeddingModels` | `boolean` | Идёт загрузка embedding-моделей |
| `chatModelsError` | `string` | Ошибка загрузки chat-моделей |
| `embeddingModelsError` | `string` | Ошибка загрузки embedding-моделей |
| `info` | `string` | Информационное сообщение пользователю |
| `isChatSettingsOpen` | `boolean` | Раскрыт/свёрнут блок «Настройки чата» |
| `isEmbeddingSettingsOpen` | `boolean` | Раскрыт/свёрнут блок «Эмбеддинг» |

#### Тип `RuntimeDraft`

```typescript
type RuntimeDraft = {
  llmBase: string;          // URL подключения (например, http://localhost:11434)
  provider: LlmProvider;    // 'none' | 'ollama' | 'openai'
  model: string;            // Выбранная chat-модель
  embeddingProvider: LlmProvider;
  embeddingModel: string;
  maxHistory: number;       // 1..50 сообщений в истории чата
  debugModelMode: boolean;  // Детальные логи отправки в консоль
};
```

Черновик сохраняется в `localStorage` по ключу `'rag.runtime-config.draft'` при любом сохранении.

#### Ключевые функции

**`acceptPort()`** — кнопка «Принять» рядом с полем URL:
- Нормализует URL.
- Если пустой — сбрасывает модели, устанавливает провайдер `none`.
- Если заполнен — устанавливает `acceptedBase`, что триггерит `useEffect` загрузки моделей.

**`connect()`** — кнопка «Подключить»:
1. Если `provider === 'none'` или пустой URL: активирует режим None.
2. Если модель не выбрана: выводит предупреждение.
3. Иначе: вызывает `setRuntimeConfig({llmBase, llmProvider, llmModel, maxHistory, debugModelMode})`.
4. Генерирует событие `'rag-runtime-config-changed'` (слушают `connectionStore` и сам компонент).

**`disconnect()`** — кнопка «Отключить»:
- Сбрасывает провайдер в `none` через `setRuntimeConfig(...)`.

**`saveDraft()`** — кнопка «Сохранить»:
- Сохраняет черновик в `localStorage` (без применения провайдера).

**`saveEmbeddingSettings()`** — кнопка «Сохранить» в блоке Эмбеддинг:
- Сохраняет черновик в `localStorage`.
- Вызывает `POST /api/settings/embedding` с `{provider, base_url, model}`.
- Бэкенд пересоздаёт движок эмбеддингов через `store.reconfigure_embedding(...)`.

#### Загрузка моделей

Два `useEffect` срабатывают при изменении `acceptedBase` или провайдера:

| useEffect | Условие | API-запрос |
|---|---|---|
| Chat models | `provider === 'ollama' && acceptedBase` | `GET /api/llm/models?provider=ollama&base_url=...&purpose=chat` |
| Embedding models | `embeddingProvider === 'ollama' && acceptedBase` | `GET /api/llm/models?provider=ollama&base_url=...&purpose=embedding` |

Для `openai`: модели в select не загружаются, показывается одна опция (значение из черновика или `gpt-4o-mini` / `text-embedding-3-small`).

#### `lib/runtime-config.ts` — конфигурация LLM

```typescript
type RuntimeConfig = {
  llmBase: string;         // base URL провайдера
  llmProvider: LlmProvider;
  llmModel: string;
  maxHistory: number;
  debugModelMode: boolean;
};
```

Хранится в памяти (`let runtimeConfig: RuntimeConfig`) и в `localStorage` (`'rag.runtime-config'`).

Функция `setRuntimeConfig(update)`: обновляет конфигурацию, сохраняет в localStorage, генерирует событие `'rag-runtime-config-changed'` на `window`.

#### `lib/clientLogger.ts` — логгер UI-событий

Функция `logClientEvent(payload)`:
- Отправляет `POST /api/client-events` с JSON `{event, notebookId?, metadata?}`.
- Используется во всех компонентах для трассировки пользовательских действий.
- Ошибки логирования проглатываются (не прерывают UI).

---

### 4.10 Компонент настроек парсинга

**Файл:** `apps/web/components/ParsingSettingsPanel.tsx`

Отображается на главном меню в секции «Глобальные настройки парсинга» для выбранного ноутбука. Управляет глобальными настройками парсинга через API.

Props: `{ notebookId: string }`.

Поля, отображаемые по методу чанкинга:

| Метод | Поля |
|---|---|
| `general` | Метод, chunk_size, chunk_overlap |
| `context_enrichment` | Метод, chunk_size, chunk_overlap, context_window, use_llm_summary |
| `hierarchy` | Метод, doc_type, chunk_size (fallback) |
| `pcr` | Метод, parent_chunk_size, child_chunk_size |
| `symbol` | Метод, symbol_separator |
| Все методы | OCR: ocr_language, ocr_enabled, auto_parse_on_upload |

Сохранение: `PATCH /api/notebooks/{notebookId}/parsing-settings`.

---

### 4.11 Индикатор подключения

**Файл:** `apps/web/components/ConnectionIndicator.tsx`

Маленький компонент, отображающий статус LLM-подключения. Рендерится на обеих страницах (main menu + notebook workspace).

- Зелёная точка + «Connected: Ollama / model-name» — если `connectionStore.isConnected = true`.
- Серая точка + «Disconnected» — если не подключено.

Данные берутся из `useConnectionStore()`, который слушает событие `'rag-runtime-config-changed'`.

---

### 4.12 Клиентские сторы (State Management)

Все сторы реализованы без внешних библиотек через `useSyncExternalStore`.

#### `src/stores/chatStore.ts`

Управляет состоянием очистки чата и активными потоками.

| Экспорт | Тип | Описание |
|---|---|---|
| `beginClear()` | `() => number` | Начало очистки: закрывает все активные потоки, возвращает clearId |
| `finishClear(id)` | `(number) => void` | Завершение очистки |
| `failClear(id)` | `(number) => void` | Отмена очистки (при ошибке API) |
| `registerStreamCloser(streamId, fn)` | — | Регистрирует функцию закрытия потока |
| `unregisterStreamCloser(streamId)` | — | Снимает регистрацию |
| `shouldIgnoreStream(startedAt)` | `boolean` | True если поток устарел из-за очистки |
| `useChatStore()` | hook | `{isClearing, pendingClearId, lastClearId}` |

#### `src/stores/modeStore.ts`

Хранит текущий режим чата, персистирует в `localStorage` по ключу `'chat-mode'`.

| Экспорт | Описание |
|---|---|
| `initializeModeStore()` | Читает из localStorage при старте |
| `setCurrentMode(mode)` | Устанавливает режим, сохраняет в localStorage |
| `useModeStore()` | `{currentMode: 'rag' \| 'model' \| 'agent'}` |

#### `src/stores/connectionStore.ts`

Производный стор от `runtimeConfig`. Слушает `'rag-runtime-config-changed'`.

| Экспорт | Описание |
|---|---|
| `initializeConnectionStore()` | Инициализирует и подписывается на событие изменения конфига |
| `setKeepAlive(bool)` | Управляет флагом keepAlive |
| `useConnectionStore()` | `{isConnected, currentModel, provider, keepAlive}` |

`isConnected = llmProvider !== 'none' && llmModel.trim().length > 0`.

#### `src/stores/agentStore.ts`

Хранит ID выбранного агента, персистирует в `localStorage` по ключу `'selected-agent-id'`.

| Экспорт | Описание |
|---|---|
| `initializeAgentStore()` | Читает из localStorage |
| `setSelectedAgent(agentId)` | Устанавливает агента, сохраняет в localStorage |
| `useAgentStore()` | `{selectedAgentId: string}` |

---

### 4.13 SSE-клиент

**Файл:** `apps/web/lib/sse.ts`

Функция `openChatStream(params)` — открывает SSE-поток к `GET /api/chat/stream`.

**Параметры:**

| Параметр | Описание |
|---|---|
| `notebookId` | ID ноутбука |
| `message` | Текст вопроса |
| `mode` | Режим чата (`'rag' \| 'model' \| 'agent'`) |
| `agentId?` | ID агента (только для `agent` режима) |
| `selectedSourceIds` | Список ID включённых источников |
| `handlers` | `{onToken, onCitations, onDone, onError}` |

**Логика:**
1. Строит URL с query-параметрами: `notebook_id`, `message`, `mode`, `selected_source_ids`, `provider`, `model`, `base_url`, `max_history`, опционально `agent_id`.
2. Создаёт `EventSource(url)`.
3. Слушает три события:
   - `token` → `onToken(text)` — добавляет токен к стриму.
   - `citations` → `onCitations(payload)` — обновляет список цитат.
   - `done` → `onDone(messageId)` — закрывает поток.
   - `error` → `onError(error)` — ошибка LLM.
4. `onerror` — обрыв соединения → `onError`.
5. Возвращает функцию закрытия `() => eventSource.close()`.

---

## 5. Backend (`apps/api`)

### 5.1 Технологический стек

| Технология | Версия/назначение |
|---|---|
| Python 3.11+ | Язык |
| FastAPI | REST API + SSE стриминг |
| Pydantic v2 | Схемы запросов/ответов, валидация |
| SQLite + sqlite-vec | Полнотекстовый (FTS5) + векторный поиск |
| httpx | Асинхронные HTTP-запросы к LLM-провайдерам |
| threading | Фоновая индексация документов |
| uvicorn | ASGI-сервер |

### 5.2 Структура файлов бэкенда

```
apps/api/
├── main.py                         # Точка входа FastAPI-приложения
├── config.py                       # Конфигурационные константы и пути
├── schemas.py                      # Pydantic-схемы (DTO)
├── store.py                        # In-memory хранилище + оркестрация
├── logging_setup.py                # Настройка логирования (2 файла: app + ui)
├── routers/
│   ├── notebooks.py                # CRUD ноутбуков + настройки парсинга
│   ├── sources.py                  # Управление источниками (upload, parse, delete)
│   ├── chat.py                     # Чат-запросы + SSE-стриминг
│   ├── notes.py                    # Заметки ноутбука
│   ├── citations.py                # Сохранённые цитаты
│   ├── global_notes.py             # Глобальные заметки (cross-notebook)
│   ├── llm.py                      # Управление LLM: список моделей, настройка эмбеддинга
│   ├── client_events.py            # Получение UI-событий от фронтенда
│   └── agents.py                   # Список агентов
└── services/
    ├── chat_modes.py               # Режимы чата, пороги релевантности
    ├── model_chat.py               # Генерация ответов + системные промпты
    ├── search_service.py           # Гибридный поиск (vector + FTS) + RRF
    ├── index_service.py            # Оркестрация индексации
    ├── parse_service.py            # Парсинг документов (PDF/DOCX/XLSX/TXT)
    ├── notebook_db.py              # SQLite БД ноутбука (документы, чанки, поиск)
    ├── global_db.py                # Глобальная SQLite БД (ноутбуки, источники)
    └── embedding_service.py        # Движок эмбеддингов (Ollama, OpenAI-compatible)
```

---

### 5.3 Точка входа — `main.py`

Создаёт экземпляр `FastAPI`, настраивает CORS и подключает роутеры.

#### Порядок инициализации при старте

1. `setup_logging()` — настраивает два лог-файла и консольный вывод (`logging_setup.py`).
2. `app = FastAPI(...)` — создание приложения.
3. `app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)` — разрешает CORS для любых источников (локальный режим).
4. Подключение всех роутеров: `app.include_router(notebooks.router)`, `...sources...`, `...chat...`, `...notes...`, `...citations...`, `...global_notes...`, `...llm...`, `...client_events...`, `...agents...`.
5. `@app.middleware("http")` — middleware логирования HTTP-запросов (метод, путь, статус, длительность в ms, IP-адрес клиента).

#### Middleware логирования

Каждый HTTP-запрос логируется с полями:
- `event = 'http.request'`
- `method`, `path`, `status_code`, `duration_ms`, `client_ip`

Запросы к `/api/chat/stream` и `/api/client-events` логируются на уровне `DEBUG` (не засоряют INFO-логи потоками токенов).

---

### 5.4 Конфигурация — `config.py`

Все конфиги — переменные окружения с дефолтами.

| Переменная | Env | Default | Описание |
|---|---|---|---|
| `ROOT_DIR` | — | `Path(__file__).parents[2]` | Корень репозитория |
| `DATA_DIR` | — | `ROOT_DIR / 'data'` | Директория данных |
| `DOCS_DIR` | — | `DATA_DIR / 'docs'` | Физические файлы документов |
| `CHUNKS_DIR` | — | `DATA_DIR / 'parsing'` | JSON-чанки |
| `NOTEBOOKS_DB_DIR` | — | `DATA_DIR / 'notebooks'` | SQLite БД ноутбуков |
| `LOGS_DIR` | — | `DATA_DIR / 'logs'` | Логи |
| `CITATIONS_DIR` | — | `DATA_DIR / 'citations'` | Сохранённые цитаты |
| `NOTES_DIR` | — | `DATA_DIR / 'notes'` | Глобальные заметки |
| `EMBEDDING_ENABLED` | `EMBEDDING_ENABLED` | `True` | Включить embedding-движок |
| `EMBEDDING_PROVIDER` | `EMBEDDING_PROVIDER` | `'ollama'` | Провайдер эмбеддингов |
| `EMBEDDING_ENDPOINT` | `EMBEDDING_ENDPOINT` | `None` | Кастомный URL endpoint |
| `EMBEDDING_DIM` | `EMBEDDING_DIM` | `384` | Размерность векторов |
| `EMBEDDING_BASE_URL` | `EMBEDDING_BASE_URL` | `'http://localhost:11434'` | URL Ollama |
| `MAX_UPLOAD_MB` | — | `25` | Максимальный размер загружаемого файла |
| `UPLOAD_MAX_BYTES` | — | `25 * 1024 * 1024` | В байтах |

---

### 5.5 Схемы данных — `schemas.py`

Pydantic-модели, описывающие DTO для REST API.

#### Основные модели

| Модель | Поля | Описание |
|---|---|---|
| `Notebook` | `id, title, created_at, updated_at` | Ноутбук |
| `Source` | `id, notebook_id, filename, file_path, file_type, size_bytes, status, added_at, is_enabled, has_docs, has_parsing, has_base, embeddings_status, index_warning, sort_order, individual_config` | Источник (файл) |
| `ParsingSettings` | `chunk_size, chunk_overlap, min_chunk_size, ocr_enabled, ocr_language, auto_parse_on_upload, chunking_method, context_window, use_llm_summary, doc_type, parent_chunk_size, child_chunk_size, symbol_separator` | Настройки парсинга |
| `ChatMessage` | `id, notebook_id, role, content, created_at` | Сообщение чата |
| `CitationLocation` | `page, sheet, paragraph` | Локация источника |
| `Citation` | `id, notebook_id, source_id, filename, location, snippet, score, doc_order` | Цитата в ответе чата |
| `SavedCitation` | `id, notebook_id, source_id, filename, doc_order, chunk_text, location, created_at, source_notebook_id, source_type` | Сохранённая пользователем цитата |
| `GlobalNote` | `id, content, source_notebook_id, source_notebook_title, created_at, source_refs` | Глобальная заметка |
| `IndexStatus` | `total, indexed, indexing, failed` | Статус индексации ноутбука |

#### Модели запросов

| Модель | Описание |
|---|---|
| `ChatRequest` | Тело запроса чата (mode, provider, model, base_url, selected_source_ids) |
| `CreateNotebookRequest` | `{title: str}` |
| `UpdateNotebookRequest` | `{title: str}` |
| `UpdateSourceRequest` | `{is_enabled?, individual_config?}` |
| `ReorderSourcesRequest` | `{ordered_ids: list[str]}` |
| `SaveCitationRequest` | Данные для сохранения цитаты |
| `CreateGlobalNoteRequest` | Данные для создания глобальной заметки |

#### Поле `Source.status`

| Значение | Описание |
|---|---|
| `'new'` | Файл загружен, парсинг не запускался |
| `'indexing'` | Парсинг/индексация в процессе (фоновый поток) |
| `'indexed'` | Успешно проиндексирован |
| `'failed'` | Ошибка при индексации |

#### Поле `Source.individual_config`

Словарь с индивидуальными параметрами парсинга для конкретного файла. `null`-значение означает «использовать глобальную настройку ноутбука»:

```python
{
  "chunk_size": None,           # int | None
  "chunk_overlap": None,        # int | None
  "ocr_enabled": None,          # bool | None
  "ocr_language": None,         # str | None
  "chunking_method": None,      # str | None
  "context_window": None,       # int | None
  "use_llm_summary": None,      # bool | None
  "doc_type": None,             # str | None
  "parent_chunk_size": None,    # int | None
  "child_chunk_size": None,     # int | None
  "symbol_separator": None,     # str | None
}
```

---

### 5.6 Хранилище данных — `store.py`

**Класс `InMemoryStore`** — центральный объект приложения. Хранит все данные в памяти (dict), персистирует в SQLite через `GlobalDB` и файловую систему.

Синглтон `store = InMemoryStore()` создаётся при старте приложения.

#### Структура хранилища

```python
class InMemoryStore:
    notebooks: dict[str, Notebook]          # {notebook_id: Notebook}
    sources: dict[str, Source]              # {source_id: Source}
    messages: dict[str, list[ChatMessage]]  # {notebook_id: [msg, ...]}
    notes: dict[str, list[Note]]            # {notebook_id: [note, ...]}
    chat_versions: dict[str, int]           # {notebook_id: version}
    parsing_settings: dict[str, ParsingSettings]  # {notebook_id: settings}
    _embedding_engine: EmbeddingEngine | None
```

#### Инициализация (`seed_data`)

При первом запуске (`__init__` → `seed_data()`):
1. Загружает все ноутбуки из `GlobalDB.load_all_notebooks()`.
2. Загружает настройки парсинга из `GlobalDB.load_all_parsing_settings()`.
3. Загружает все источники из `GlobalDB.load_all_sources()`, исправляя:
   - `has_docs = False` если файл физически удалён.
   - `status = 'failed'` если был `'indexing'` (прерван перезапуском).
4. Если ноутбуков нет — создаёт демо-ноутбук с двумя sample-файлами (`_seed_demo()`).

#### Ключевые методы

| Метод | Описание |
|---|---|
| `create_notebook(title)` | Создаёт ноутбук + директорию `docs/{id}` + персистирует в `GlobalDB` |
| `update_notebook_title(id, title)` | Обновляет заголовок + `updated_at` |
| `delete_notebook(id)` | Удаляет файлы, JSON-чанки, SQLite БД, цитаты, заметки, запись в `GlobalDB` |
| `duplicate_notebook(id)` | Копирует файлы, JSON-чанки, SQLite БД с ремаппингом source_id |
| `add_source_from_path(nb_id, path, indexed)` | Создаёт запись `Source`, опционально запускает фоновую индексацию |
| `save_upload(nb_id, filename, content)` | Записывает байты на диск (с разрешением коллизий имён) + вызывает `add_source_from_path` |
| `reparse_source(source_id)` | Сбрасывает статус в `indexing`, запускает фоновый поток |
| `delete_source_fully(source_id)` | Файл + JSON + SQLite-запись + GlobalDB + ренумерация `sort_order` |
| `delete_source_file(source_id)` | Только физический файл, `has_docs = False` |
| `erase_source_data(source_id)` | Только JSON-чанки + SQLite-данные, файл сохраняется |
| `reorder_sources(nb_id, ids)` | Обновляет `sort_order` через `GlobalDB.reorder_sources` |
| `sync_source_enabled(source_id, enabled)` | Обновляет `is_enabled` в SQLite БД ноутбука |
| `reconfigure_embedding(provider, base_url, model)` | Пересоздаёт `EmbeddingEngine` + вызывает `search_service.reconfigure_engine` |
| `save_citation(...)` | Записывает JSON-файл цитаты в `CITATIONS_DIR/{nb_id}` |
| `list_saved_citations(nb_id)` | Читает все JSON-файлы цитат ноутбука |
| `save_global_note(...)` | Записывает JSON-файл заметки в `NOTES_DIR` |
| `list_global_notes()` | Читает все JSON-файлы заметок |

#### Фоновая индексация (`_index_source_sync`)

Запускается в daemon-потоке. Порядок шагов:
1. `source.status = 'indexing'`
2. Объединяет `individual_config` источника с глобальными `parsing_settings`.
3. Вызывает `index_service.index_source(nb_id, src_id, file_path, parser_config)` → парсинг файла.
4. Вызывает `EmbeddingEngine.embed_document_from_parsing(nb_id, src_id)` → получает векторы.
5. Вызывает `NotebookDB.upsert_document(metadata, embedded_chunks)` → записывает в SQLite.
6. Устанавливает `source.status = 'indexed'` + обновляет `embeddings_status`.
7. При ошибке: `source.status = 'failed'` + персистирует через `GlobalDB`.

---

### 5.7 Роутеры

#### 5.7.1 Ноутбуки — `routers/notebooks.py`

Prefix: `/api`

| Метод | Маршрут | Функция | Описание |
|---|---|---|---|
| `GET` | `/notebooks` | `list_notebooks()` | Список всех ноутбуков |
| `POST` | `/notebooks` | `create_notebook(payload)` | Создать ноутбук |
| `GET` | `/notebooks/{id}` | `get_notebook(id)` | Получить один ноутбук |
| `PATCH` | `/notebooks/{id}` | `update_notebook(id, payload)` | Переименовать |
| `POST` | `/notebooks/{id}/duplicate` | `duplicate_notebook(id)` | Дублировать |
| `DELETE` | `/notebooks/{id}` | `delete_notebook(id)` | Удалить |
| `GET` | `/notebooks/{id}/index/status` | `index_status(id)` | Статус индексации (total/indexed/indexing/failed) |
| `GET` | `/notebooks/{id}/parsing-settings` | `get_parsing_settings(id)` | Настройки парсинга |
| `PATCH` | `/notebooks/{id}/parsing-settings` | `update_parsing_settings(id, payload)` | Обновить настройки парсинга |

#### 5.7.2 Источники — `routers/sources.py`

Prefix: `/api`

| Метод | Маршрут | Функция | Описание |
|---|---|---|---|
| `GET` | `/notebooks/{id}/sources` | `list_sources(id)` | Список источников ноутбука (сортировка по `sort_order`) |
| `POST` | `/notebooks/{id}/sources/upload` | `upload_source(id, file)` | Загрузить файл (multipart, max 25 MB) |
| `POST` | `/notebooks/{id}/sources/add-path` | `add_source_path(id, payload)` | Добавить файл по пути (для desktop) |
| `PATCH` | `/notebooks/{id}/sources/reorder` | `reorder_sources(id, payload)` | Сохранить новый порядок |
| `DELETE` | `/notebooks/{id}/sources/files` | `delete_all_source_files(id)` | Удалить все физические файлы ноутбука |
| `GET` | `/sources/{source_id}` | `get_source(source_id)` | Получить источник |
| `PATCH` | `/sources/{source_id}` | `update_source(source_id, payload)` | Обновить `is_enabled`/`individual_config` |
| `DELETE` | `/sources/{source_id}` | `delete_source(source_id)` | Удалить источник полностью |
| `DELETE` | `/sources/{source_id}/erase` | `erase_source(source_id)` | Стереть данные (файл сохранить) |
| `POST` | `/sources/{source_id}/reparse` | `reparse_source(source_id)` | Перезапустить индексацию |
| `POST` | `/sources/{source_id}/open` | `open_source(source_id)` | Открыть файл системным приложением |
| `GET` | `/files` | `get_file(path)` | Отдать файл по пути (для просмотра в браузере) |

**Загрузка файла** (`upload_source`):
1. Проверяет размер: `>= UPLOAD_MAX_BYTES (25 MB)` → `HTTP 413`.
2. `await store.save_upload(notebook_id, filename, content)`.
3. Если `auto_parse_on_upload = True` — индексация запускается автоматически.

**Обновление источника** (`update_source`):
- При изменении `is_enabled` дополнительно вызывает `store.sync_source_enabled(source_id, enabled)` — синхронизирует флаг в SQLite БД ноутбука.

#### 5.7.3 Чат и SSE — `routers/chat.py`

Prefix: `/api`

| Метод | Маршрут | Функция | Описание |
|---|---|---|---|
| `GET` | `/notebooks/{id}/messages` | `list_messages(id)` | История чата |
| `DELETE` | `/notebooks/{id}/messages` | `clear_chat(id)` | Очистить историю чата |
| `GET` | `/chat/stream` | `chat_stream(...)` | SSE-стриминг ответа |

**`GET /api/chat/stream`** — основной эндпоинт чата.

Query-параметры: `notebook_id`, `message`, `mode` (`rag|model|agent`), `selected_source_ids` (через запятую), `provider`, `model`, `base_url`, `max_history` (default 5), `agent_id`.

**Порядок обработки чат-запроса:**

```
1. Нормализация режима: normalize_chat_mode(raw_mode)
   → "rag" | "model" | "agent"

2. Получить историю: messages = store.messages[notebook_id][-max_history:]
   build_chat_history(messages, max_history) → list[{role, content}]

3. Добавить сообщение пользователя: store.add_message(nb_id, "user", message)

4. Поиск источников (для rag и model):
   4.1 search_service.search(nb_id, message, selected_ids, top_n=5)
       → vector search (cosine) + FTS5 (BM25) → RRF merge
   4.2 normalize_chunk_scores(chunks) → [0..1]
   4.3 filter_chunks_by_threshold(chunks, threshold)
       → rag: 0.75, model: 0.50
   4.4 chunk_to_citation_fields(chunk) → filename, page, section

5. Режим RAG без источников:
   → Вернуть RAG_NO_SOURCES_MESSAGE (без LLM-вызова)

6. Режим Agent:
   → Вернуть build_answer("agent", message, [], agent_id)

7. Генерация ответа (model / rag с источниками):
   7.1 build_rag_context(chunks, source_order_map) → строка с [N] ссылками
   7.2 build_messages_for_mode(mode, history, rag_context, sources_found)
       → системный промпт + история
   7.3 stream_model_answer(provider, base_url, model, messages, ...) → async gen

8. SSE-стриминг клиенту:
   - event: "token" → {"text": "<токен>"}
   - event: "citations" → [{id, filename, snippet, score, ...}, ...]
   - event: "done" → {"message_id": "<uuid>"}
   - event: "error" → {"detail": "..."} (при ошибке LLM)

9. После завершения: store.add_message(nb_id, "assistant", full_answer)
```

**Формирование `EventSourceResponse`:**

FastAPI возвращает `EventSourceResponse` (из `sse-starlette`), который создаёт async-генератор, отправляющий события в формате:
```
event: token\ndata: {"text": "..."}\n\n
event: citations\ndata: [{...}]\n\n
event: done\ndata: {"message_id": "..."}\n\n
```

#### 5.7.4 Заметки ноутбука — `routers/notes.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/notebooks/{id}/notes` | Список заметок ноутбука |
| `POST` | `/api/notebooks/{id}/notes` | Создать заметку |

Заметки ноутбука хранятся только в памяти (`store.notes`), не персистируются между перезапусками.

#### 5.7.5 Сохранённые цитаты — `routers/citations.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/notebooks/{id}/saved-citations` | Список сохранённых цитат |
| `POST` | `/api/notebooks/{id}/saved-citations` | Сохранить цитату |
| `DELETE` | `/api/notebooks/{id}/saved-citations/{citation_id}` | Удалить цитату |

Цитаты персистируются в `data/citations/{nb_id}/{citation_id}.json`.

#### 5.7.6 Глобальные заметки — `routers/global_notes.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/notes` | Список всех глобальных заметок |
| `POST` | `/api/notes` | Создать глобальную заметку |
| `DELETE` | `/api/notes/{note_id}` | Удалить глобальную заметку |

Заметки персистируются в `data/notes/{note_id}.json`.

#### 5.7.7 LLM-провайдер — `routers/llm.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/llm/models` | Список доступных моделей Ollama |
| `POST` | `/api/settings/embedding` | Применить конфигурацию эмбеддингов |

**`GET /api/llm/models`**
Query: `provider`, `base_url`, `purpose` (`all|chat|embedding`).
- Запрашивает `GET {base_url}/api/tags` у Ollama.
- Фильтрует модели по назначению (keyword-based: `embed`, `bge`, `e5` → embedding; остальные → chat).

**`POST /api/settings/embedding`**
Тело: `{provider, base_url, model}`.
Вызывает `store.reconfigure_embedding(provider, base_url, model)` → пересоздаёт `EmbeddingEngine`.

#### 5.7.8 Клиентские события — `routers/client_events.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `POST` | `/api/client-events` | Принять событие от фронтенда и записать в ui_*.log |

Тело: `{event: str, notebookId?: str, metadata?: dict}`.
Логирует через стандартный logger с `extra={"event": f"client.{event}"}`.
Эти события попадают в `ui_{SESSION_ID}.log` (фильтр `_OnlyClientEventsFilter`).

#### 5.7.9 Агенты — `routers/agents.py`

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/agents` | Список агентов (читает `agent_manifest.json` из `agent/` директорий) |

---

### 5.8 Сервисы

#### 5.8.1 Режимы чата — `services/chat_modes.py`

Определяет режимы чата как замороженные датаклассы.

```python
CHAT_MODE_SPECS = (
    ChatModeSpec(code="model", title="Модель", uses_retrieval=False),
    ChatModeSpec(code="agent", title="Агент",  uses_retrieval=False),
    ChatModeSpec(code="rag",   title="RAG",    uses_retrieval=True),
)
```

Пороги релевантности (для нормализованных RRF-оценок):

| Режим | Порог | Логика |
|---|---|---|
| `rag` | 0.75 | Строгий: только высокорелевантные чанки |
| `model` | 0.50 | Мягкий: чанки не менее 50% от лучшего результата |

`normalize_chat_mode(raw_mode)` — нормализует и валидирует входной режим, при неизвестном возвращает `DEFAULT_CHAT_MODE = "rag"`.

#### 5.8.2 Генерация ответов — `services/model_chat.py`

Отвечает за коммуникацию с LLM-провайдером и формирование системных промптов.

**Системные промпты (3 варианта):**

| Константа | Режим | Условие |
|---|---|---|
| `_SYSTEM_RAG_WITH_SOURCES` | rag | Всегда (если вызывается при наличии источников) |
| `_SYSTEM_MODEL_WITH_SOURCES` | model | Источники найдены |
| `_SYSTEM_MODEL_NO_SOURCES` | model | Источники не найдены |

**`build_chat_history(messages, limit)`**:
- Берёт последние `limit` сообщений из истории.
- Преобразует в `[{role, content}, ...]`.

**`build_rag_context(chunks, source_order_map)`**:
- Формирует строку из фрагментов для вставки в системный промпт.
- Каждый фрагмент: `[N] filename.ext (стр. M):\n<текст>`.
- `N` = `source_order_map[source_id]` (порядковый номер документа в ноутбуке) или `i` (порядковый номер среди retrieved чанков).

**`build_messages_for_mode(chat_mode, history, rag_context, sources_found)`**:
- Выбирает нужный системный промпт.
- Возвращает `[{role: "system", content: ...}, ...history]`.

**`stream_model_answer(...)`** — async-генератор стриминга:
1. Нормализует провайдера и URL.
2. Для `ollama`: `POST {base_url}/api/chat` с `{stream: true}`, парсит `message.content` из NDJSON.
3. Для `openai`-compatible: `POST {base_url}/v1/chat/completions` с `{stream: true}`, парсит `data: {choices: [{delta: {content}}]}` из SSE.
4. Yield'ит строковые токены.
5. При `httpx.HTTPError` бросает `RuntimeError` (ловится роутером `chat.py`).

**`generate_model_answer(...)`** — не-стриминговый вариант (используется в агент-режиме будущего).

#### 5.8.3 Гибридный поиск — `services/search_service.py`

**`search(notebook_id, message, selected_source_ids, top_n=5)`**:

1. Инициализирует `EmbeddingEngine` лениво (один раз за жизнь процесса).
2. Если движок доступен: `engine.embed_query(message)` → вектор запроса.
3. `NotebookDB.search_vector(query_vector, top_k=max(top_n*3,10))` → косинусное сходство.
4. `NotebookDB.search_fts(query, top_k=max(top_n*3,10))` → BM25.
5. `_rrf_merge(vector_rows, fts_rows, top_n)` → Reciprocal Rank Fusion.
6. Возвращает список словарей с полями: `source_id`, `source`, `page`, `section_id`, `section_title`, `text`, `type`, `doc_id`, `score`.

**`_rrf_merge(vector_rows, fts_rows, top_n)`**:
- `k = 60` (константа сглаживания).
- Для каждой позиции ранга: `score += 1 / (k + rank)`.
- Объединяет два ранжированных списка по `chunk_id`.
- Возвращает топ-N по суммарному RRF-score.

**`normalize_chunk_scores(chunks)`**:
- Нормализует поле `score` к `[0, 1]` относительно максимума.
- Если максимум = 0 (нет эмбеддингов, только FTS): всем `score = 1.0`.

**`filter_chunks_by_threshold(chunks, threshold)`**:
- Фильтрует чанки по `score >= threshold`.

**`reconfigure_engine(provider, base_url, model_name)`**:
- Сбрасывает `_ENGINE = None`.
- При следующем вызове `_engine()` — создаётся новый с новыми параметрами.

#### 5.8.4 Индексация — `services/index_service.py`

**`index_source(notebook_id, source_id, file_path, *, parser_config, source_state)`**:
- Создаёт `DocumentParser(ParserConfig(**parser_config))`.
- Вызывает `parser.parse(filepath, notebook_id, metadata_override)`.
- Возвращает `(metadata, chunks_list)`.

**`get_notebook_blocks(notebook_id)`**:
- Читает все чанки из SQLite БД ноутбука (для внешнего использования/отладки).

#### 5.8.5 Парсинг документов — `services/parse_service.py`

Основная логика: класс `DocumentParser` с конфигурацией `ParserConfig`.

**Поддерживаемые форматы:**

| Формат | Метод |
|---|---|
| PDF | PyMuPDF + опциональный Tesseract OCR для сканов |
| DOCX | python-docx |
| XLSX | openpyxl |
| TXT / другие | Прямое чтение текста |

**Методы чанкинга:**

| Метод | Описание |
|---|---|
| `general` | Посимвольное деление с перекрытием (`chunk_size`, `chunk_overlap`) |
| `context_enrichment` | `general` + обогащение чанков соседним контекстом (`context_window` символов) |
| `hierarchy` | Деление по структуре документа (заголовки, разделы). Тип документа задаётся `doc_type` |
| `pcr` | Parent-Child Retrieval: крупные родительские чанки + мелкие дочерние для поиска |
| `symbol` | Разделение по кастомному символу-разделителю (`symbol_separator`) |

**`parse(filepath, notebook_id, metadata_override)`** возвращает:
- `DocumentMetadata` — метаданные файла (doc_id, filename, filepath, file_hash, size_bytes, title, authors, year, tags).
- `list[dict]` — список чанков с полями: `chunk_id`, `chunk_index`, `page_number`, `chunk_type`, `section_header`, `parent_header`, `text`, `token_count`, `embedding_text`, `parent_chunk_id`.

Результат сохраняется в JSON: `data/parsing/{notebook_id}/{source_id}.json`.

#### 5.8.6 SQLite БД ноутбука — `services/notebook_db.py`

Класс `NotebookDB(notebook_id)` — открывает/создаёт файл `data/notebooks/{id}.db`.

**Схема БД:**

| Таблица | Назначение |
|---|---|
| `documents` | Метаданные документов: `doc_id, source_id, filename, filepath, file_hash, ...` |
| `chunks` | Чанки: `chunk_id, doc_id, chunk_index, page_number, chunk_type, section_header, chunk_text, token_count, embedding_text, parent_chunk_id` |
| `chunks_fts` | Виртуальная FTS5-таблица для полнотекстового поиска по `chunk_text` |
| `chunk_embeddings` | Векторные представления: `chunk_rowid, embedding (JSON)` |
| `tags` | Теги: `tag, is_enabled` |
| `document_tags` | Связь документ-тег |

**Конфигурация SQLite:**
- `PRAGMA journal_mode=WAL` — write-ahead logging для concurrent read.
- `PRAGMA synchronous=NORMAL` — баланс скорость/надёжность.
- `PRAGMA foreign_keys=ON` — каскадное удаление чанков при удалении документа.
- `PRAGMA cache_size=-64000` — 64 MB кэш.
- `sqlite_vec` — расширение для ускорения векторного поиска (подключается если доступно).

**Ключевые методы:**

| Метод | Описание |
|---|---|
| `upsert_document(metadata, embedded_chunks, tags, is_enabled)` | INSERT OR UPDATE документа + удаление старых чанков + вставка новых |
| `set_document_enabled(doc_id, enabled)` | Обновить `is_enabled` |
| `search_fts(query, top_k, selected_ids, only_enabled_tags)` | BM25-поиск. Fallback: LIKE-поиск, затем последние N чанков |
| `search_vector(query_vector, top_k, selected_ids, only_enabled_tags)` | Косинусное сходство: вычисляется в Python (loop через JSON-векторы) |
| `_enabled_filter_clause(selected_ids, only_enabled_tags)` | Формирует SQL WHERE с фильтрами enabled-документов, тегов и выбранных источников |

#### 5.8.7 Глобальная БД — `services/global_db.py`

Файл: `data/store.db`. Thread-safe (использует `threading.Lock`).

Таблицы: `notebooks`, `sources`, `parsing_settings`.

**Ключевые методы:**

| Метод | Описание |
|---|---|
| `upsert_notebook(id, title, created_at, updated_at)` | INSERT OR UPDATE ноутбука |
| `delete_notebook(notebook_id)` | Каскадное удаление (sources + parsing_settings + notebook) |
| `load_all_notebooks()` | Загрузить все ноутбуки при старте |
| `upsert_source(src_dict)` | INSERT OR UPDATE источника |
| `delete_source(source_id)` | Удалить запись источника |
| `get_max_sort_order(notebook_id)` | Текущий максимальный sort_order |
| `reorder_sources(notebook_id, ordered_ids)` | Установить sort_order по переданному порядку |
| `renumber_sort_orders(notebook_id)` | Перенумеровать 1..N после удаления |
| `load_all_sources()` | Загрузить все источники при старте (нормализует типы полей) |
| `upsert_parsing_settings(...)` | INSERT OR UPDATE настроек парсинга |
| `load_all_parsing_settings()` | Загрузить все настройки при старте |

**Миграция** (`_migrate`): добавляет новые колонки к существующим БД (idempotent `ALTER TABLE ADD COLUMN`). Порядок: сначала ALTER-операции, затем CREATE TABLE IF NOT EXISTS.

#### 5.8.8 Сервис эмбеддингов — `services/embedding_service.py`

Класс `EmbeddingEngine(config)` — обёртка над провайдером эмбеддингов.

**`embed_query(text)`** — получает вектор для текста запроса.

**`embed_document_from_parsing(notebook_id, source_id)`** → `list[EmbeddedChunk]`:
1. Читает JSON-файл чанков `data/parsing/{nb_id}/{src_id}.json`.
2. Для каждого чанка вызывает провайдер → получает вектор.
3. Если провайдер недоступен — создаёт `EmbeddedChunk` с `embedding_failed=True` (пустой вектор).

Для Ollama: `POST {base_url}/api/embed` с `{model, input: text}`.

Класс `EmbeddedChunk`:
```python
@dataclass
class EmbeddedChunk:
    parsed_chunk: dict      # Оригинальный чанк с текстом/метаданными
    embedding: list[float]  # Вектор (dim = EMBEDDING_DIM)
    meta: ChunkMeta         # token_count
    embedding_failed: bool  # True если эмбеддинг не получен
```

---

### 5.9 Логирование — `logging_setup.py`

При каждом запуске бэкенда создаётся уникальный `SESSION_ID` (timestamp).

**Два файла логов:**
- `data/logs/sessions/app_{SESSION_ID}.log` — серверные события.
- `data/logs/sessions/ui_{SESSION_ID}.log` — клиентские UI-события.

**Ротация:** каждые 4 часа, хранится до 12 файлов на сессию.

**Фильтрация:**
- `app_*.log` — всё, кроме `event.startswith('client.')`.
- `ui_*.log` — только `event.startswith('client.')`.

**Формат app-логов:**
```
timestamp | LEVEL | logger | message | event=... | method=... | path=... | status=... | duration_ms=... | ip=... | details=...
```

---

## 6. Ключевые потоки данных

### 6.1 Загрузка и индексация документа

```
Пользователь → [Upload] → SourcesPanel.onUpload
    ↓
page.uploadSource.mutate(file)
    ↓
POST /api/notebooks/{id}/sources/upload  [multipart, max 25 MB]
    ↓
store.save_upload(nb_id, filename, bytes)
    → записывает bytes на диск: data/docs/{nb_id}/{filename}
    → store.add_source_from_path(nb_id, path, indexed=False)
        → Source{status='new'|'indexing'}
        → если auto_parse_on_upload: запускает _index_source_sync в daemon-thread
    ↓
Ответ: Source{status='new'|'indexing'}
    ↓
[Пользователь нажимает ▶] → store.reparse_source(source_id)
    ↓
_index_source_sync(source_id):
    1. source.status = 'indexing'
    2. DocumentParser.parse(file_path) → metadata, chunks_list
       → сохраняет data/parsing/{nb_id}/{src_id}.json
    3. EmbeddingEngine.embed_document_from_parsing(nb_id, src_id)
       → POST {ollama_url}/api/embed для каждого чанка
    4. NotebookDB.upsert_document(metadata, embedded_chunks)
       → INSERT INTO documents, chunks, chunks_fts, chunk_embeddings
    5. source.status = 'indexed'
    6. GlobalDB.upsert_source(source)  ← персистирует статус
```

### 6.2 Чат-запрос в режиме RAG

```
Пользователь → [Отправить] → ChatPanel.onSend(text)
    ↓
page.sendMessage(text)
    ↓
openChatStream({notebookId, message, mode='rag', selectedSourceIds, ...})
    → EventSource → GET /api/chat/stream?...
    ↓
router.chat_stream(...)
    1. normalize_chat_mode('rag') → 'rag'
    2. build_chat_history(messages, max_history) → list[{role, content}]
    3. store.add_message(nb_id, 'user', message)
    4. search_service.search(nb_id, message, selected_ids, top_n=5)
       → EmbeddingEngine.embed_query(message) → query_vector
       → NotebookDB.search_vector(query_vector) → vector_rows
       → NotebookDB.search_fts(message) → fts_rows
       → _rrf_merge(vector_rows, fts_rows) → merged_chunks
    5. normalize_chunk_scores(merged_chunks)
    6. filter_chunks_by_threshold(chunks, threshold=0.75)
    7. Если пусто → yield event:token + event:done (RAG_NO_SOURCES_MESSAGE)
    8. build_rag_context(chunks, source_order_map)
    9. stream_model_answer(provider, base_url, model, history, rag_context, mode='rag')
       → POST {ollama_url}/api/chat (stream=True)
       → async for token: yield event:token
    10. yield event:citations ([{id, filename, score, snippet, ...}])
    11. yield event:done ({message_id})
    12. store.add_message(nb_id, 'assistant', full_answer)
    ↓
EventSource handlers:
    onToken(text) → streaming += text → ChatPanel re-renders
    onCitations(data) → citations = data
    onDone(messageId) → finalize, refetch messages
```

### 6.3 Сохранение цитаты

```
Пользователь → [N] в тексте ответа
    ↓
CitationRef.onClick → page.onCitationClick(citation)
    ↓
saveCitation.mutate({source_id, filename, chunk_text, page, ...})
    ↓
POST /api/notebooks/{id}/saved-citations
    ↓
store.save_citation(...) → data/citations/{nb_id}/{citation_id}.json
    ↓
queryClient.invalidateQueries(['saved-citations', notebookId])
    ↓
EvidencePanel обновляется, цитата появляется во вкладке «Цитаты»
```

---

## 7. API-контракты (полный перечень эндпоинтов)

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/notebooks` | Список ноутбуков |
| `POST` | `/api/notebooks` | Создать ноутбук |
| `GET` | `/api/notebooks/{id}` | Получить ноутбук |
| `PATCH` | `/api/notebooks/{id}` | Переименовать ноутбук |
| `POST` | `/api/notebooks/{id}/duplicate` | Дублировать ноутбук |
| `DELETE` | `/api/notebooks/{id}` | Удалить ноутбук |
| `GET` | `/api/notebooks/{id}/index/status` | Статус индексации |
| `GET` | `/api/notebooks/{id}/parsing-settings` | Настройки парсинга |
| `PATCH` | `/api/notebooks/{id}/parsing-settings` | Обновить настройки парсинга |
| `GET` | `/api/notebooks/{id}/sources` | Список источников |
| `POST` | `/api/notebooks/{id}/sources/upload` | Загрузить файл |
| `POST` | `/api/notebooks/{id}/sources/add-path` | Добавить по пути |
| `PATCH` | `/api/notebooks/{id}/sources/reorder` | Изменить порядок |
| `DELETE` | `/api/notebooks/{id}/sources/files` | Удалить все файлы |
| `GET` | `/api/notebooks/{id}/messages` | История чата |
| `DELETE` | `/api/notebooks/{id}/messages` | Очистить чат |
| `GET` | `/api/notebooks/{id}/notes` | Заметки ноутбука |
| `POST` | `/api/notebooks/{id}/notes` | Создать заметку |
| `GET` | `/api/notebooks/{id}/saved-citations` | Сохранённые цитаты |
| `POST` | `/api/notebooks/{id}/saved-citations` | Сохранить цитату |
| `DELETE` | `/api/notebooks/{id}/saved-citations/{cit_id}` | Удалить цитату |
| `GET` | `/api/sources/{id}` | Получить источник |
| `PATCH` | `/api/sources/{id}` | Обновить источник |
| `DELETE` | `/api/sources/{id}` | Удалить источник |
| `DELETE` | `/api/sources/{id}/erase` | Стереть данные парсинга |
| `POST` | `/api/sources/{id}/reparse` | Перепарсить |
| `POST` | `/api/sources/{id}/open` | Открыть в ОС |
| `GET` | `/api/files` | Отдать файл по пути |
| `GET` | `/api/chat/stream` | SSE-стриминг чата |
| `GET` | `/api/llm/models` | Список моделей LLM |
| `POST` | `/api/settings/embedding` | Применить конфигурацию эмбеддинга |
| `GET` | `/api/notes` | Глобальные заметки |
| `POST` | `/api/notes` | Создать глобальную заметку |
| `DELETE` | `/api/notes/{id}` | Удалить глобальную заметку |
| `GET` | `/api/agents` | Список агентов |
| `POST` | `/api/client-events` | Принять UI-событие |

---

## 8. Agent (`agent/`)

### Структура

```
agent/
├── agent_001/
│   ├── agent_manifest.json     # Манифест агента (id, name, description, version)
│   └── agent.py                # Реализация агента (заглушка)
└── agent_002/
    └── agent_manifest.json     # Манифест агента (только манифест, реализация не добавлена)
```

**`GET /api/agents`** возвращает список манифестов из всех поддиректорий `agent/`.

Режим `agent` в чате передаёт `agent_id` в SSE-запрос. Бэкенд возвращает заглушечный ответ `"Агент [agent_001]: режим находится в разработке."`.

---

## 9. Запуск

### 9.1 Переменные окружения (`.env`)

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000   # URL бэкенда для фронтенда
EMBEDDING_PROVIDER=ollama                    # Провайдер эмбеддингов
EMBEDDING_BASE_URL=http://localhost:11434    # URL Ollama
EMBEDDING_MODEL=nomic-embed-text             # Модель эмбеддингов
EMBEDDING_DIM=384                            # Размерность вектора
EMBEDDING_ENABLED=1                          # 0 = отключить векторный поиск
DEBUG_MODEL_MODE=0                           # 1 = детальные логи LLM
```

### 9.2 Запуск для разработки

**Linux/macOS:**
```bash
make dev
# или
./scripts/dev_run.sh
```

**Windows:**
```bat
launch.bat
```

**Вручную:**
```bash
# Бэкенд
cd apps/api
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

# Фронтенд
cd apps/web
npm install
npm run dev
# Открыть http://localhost:3000
```

### 9.3 Порты

| Сервис | Порт | По умолчанию |
|---|---|---|
| Бэкенд (FastAPI) | 8000 | `http://localhost:8000` |
| Фронтенд (Next.js) | 3000 | `http://localhost:3000` |
| Ollama | 11434 | `http://localhost:11434` |

---

## 10. Типы данных (TypeScript)

**Файл:** `apps/web/types/dto.ts`

Содержит Zod-схемы и TypeScript-типы для всех DTO, зеркалирующие Pydantic-модели бэкенда.

| TypeScript-тип | Zod-схема | Соответствие бэкенду |
|---|---|---|
| `Notebook` | `NotebookSchema` | `schemas.Notebook` |
| `Source` | `SourceSchema` | `schemas.Source` |
| `ChatMessage` | `ChatMessageSchema` | `schemas.ChatMessage` |
| `Citation` | `CitationSchema` | `schemas.Citation` |
| `SavedCitation` | `SavedCitationSchema` | `schemas.SavedCitation` |
| `GlobalNote` | `GlobalNoteSchema` | `schemas.GlobalNote` |
| `Note` | `NoteSchema` | `schemas.Note` |
| `ParsingSettings` | `ParsingSettingsSchema` | `schemas.ParsingSettings` |
| `AgentManifest` | `AgentManifestSchema` | `agent_manifest.json` |
| `IndividualConfig` | — | `Source.individual_config` |

Перечисляемые значения (константы для select-компонентов):

```typescript
CHUNKING_METHODS = ['general', 'context_enrichment', 'hierarchy', 'pcr', 'symbol']
DOC_TYPES = ['technical_manual', 'scientific_article', 'legal', 'financial', 'general']
```

---
