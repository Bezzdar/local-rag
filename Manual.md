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
