# Local RAG Assistant

Локальный ассистент для работы с документами, построенный по принципу NotebookLM.
Позволяет загружать PDF, DOCX, XLSX и текстовые файлы, задавать вопросы на естественном языке и получать ответы со ссылками на конкретные фрагменты документов.

## Описание

**Local RAG Assistant** — это локальное веб-приложение с архитектурой RAG (Retrieval-Augmented Generation), работающее полностью на вашем компьютере без отправки данных в облако.

Ключевой сценарий:

1. Создайте **ноутбук** — рабочее пространство для набора документов.
2. Загрузите файлы (PDF, DOCX, XLSX, TXT). Система автоматически проиндексирует их.
3. Задайте вопрос в чате — ассистент найдёт релевантные фрагменты и сформирует ответ со ссылками (citations) на источники.

---

## Функционал

### Работа с документами
- Загрузка файлов форматов: **PDF, DOCX, XLSX, TXT, LOG**
- Автоматическое извлечение текста, очистка и секционирование
- 5 настраиваемых методов чанкинга (разбиения на фрагменты)
- Двойной клик по источнику — открытие файла в превью или в ОС
- Нумерация источников, массовые операции (выделить/удалить/снять выделение)

### Режимы ответа чата
| Режим | Описание |
|-------|----------|
| **QA** | Ответ на вопрос с citations из документов |
| **Draft** | Составление черновика текста по материалам |
| **Table** | Структурированный вывод в виде таблицы |
| **Summarize** | Краткое резюме выбранных источников |

### Режимы работы поиска
| Режим | Описание |
|-------|----------|
| **RAG strict** | Ответ строго на основе проиндексированных документов |
| **Model analytical** | Аналитический режим с расширенными возможностями рассуждений |

### Организация работы
- **Ноутбуки** — изолированные рабочие пространства с отдельными наборами документов
- **Citations** — панель доказательств: показывает конкретный фрагмент и страницу источника
- **Notes** — сохранение ответов ассистента в заметки ноутбука
- Изменяемая ширина боковых панелей, сворачивание/разворачивание

### Логирование
- Серверный лог (`app_*.log`) — HTTP-запросы, индексация, ошибки
- UI-лог (`ui_*.log`) — действия пользователя
- Автоматическая ротация каждые 4 часа

---

## Требования

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| **Python** | 3.10+ (рекомендуется 3.11) | с опцией «Add python.exe to PATH» |
| **Node.js** | 20 LTS | 64-битная версия |
| **npm** | входит в Node.js | |
| **Git** | любая актуальная | |
| **Microsoft Visual C++ Redistributable** | 2015–2022 | требуется на Windows для части Python-пакетов |

Проверка установленных версий:

```bat
python --version && node --version && npm --version && git --version
```

---

## Установка и запуск

### Быстрый запуск — Windows (рекомендуется)

В корне репозитория находится `launch.bat` — интерактивный лаунчер.

```bat
launch.bat
```

При первом запуске (пункт **2. Запустить программу**) лаунчер автоматически:
- создаёт виртуальное окружение Python (`.venv`);
- устанавливает backend-зависимости (`pip install`);
- создаёт `apps/web/.env.local` из `.env.example`;
- запускает API-сервер (uvicorn) и Web-сервер (npm run dev) в отдельных окнах.

После запуска приложение доступно по адресам:

- **Web-интерфейс:** <http://localhost:3000>
- **API:** <http://127.0.0.1:8000>
- **Swagger UI:** <http://127.0.0.1:8000/docs>

**Меню лаунчера:**

| Пункт | Действие |
|-------|----------|
| **1. Обновление с GitHub** | `git pull --rebase` + обновление `pip` и `npm` зависимостей + очистка `.next` |
| **2. Запустить программу** | Создаёт venv (если нет), запускает API и Web |
| **3. Откат настроек** | Удаляет `data/docs`, `data/notebooks`, `data/parsing`, сбрасывает `.env.local` |
| **4. Логи** | Подменю просмотра лог-файлов |
| **0. Выход** | Закрыть лаунчер |

**Подменю «Логи»:**

| Пункт | Действие |
|-------|----------|
| **A** | Открыть окно с серверным логом (`app_*.log`) |
| **B** | Открыть окно с UI-событиями (`ui_*.log`) |
| **C** | Открыть папку `data/logs/sessions` в Проводнике |
| **0** | Назад в главное меню |

---

### Ручная установка (Windows — шаг за шагом)

#### 1. Клонирование репозитория

```bat
git clone <URL_репозитория>
cd RAG
```

#### 2. Виртуальное окружение Python и зависимости backend

**cmd.exe:**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r apps\api\requirements.txt
```

**PowerShell** (если активация не работает — сначала выполните `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r apps/api/requirements.txt
```

#### 3. Установка frontend

Во втором терминале (из корня репозитория):

```bat
copy .env.example apps\web\.env.local
cd apps\web
npm install
```

#### 4. Запуск API backend

В первом терминале (с активированным venv):

```bat
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5. Запуск Web frontend

Во втором терминале (в папке `apps/web`):

```bat
npm run dev
```

#### 6. Проверка

Откройте <http://localhost:3000>, создайте ноутбук, загрузите документ и задайте вопрос.

---

### Быстрый запуск — Linux / macOS

```bash
# 1. Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt

# 2. Запуск API
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Frontend (в другом терминале)
cd apps/web
cp ../../.env.example .env.local
npm install
npm run dev
```

---

### Offline-установка (Python)

Для окружений без доступа к PyPI:

```bash
# На машине с интернетом — скачать wheel-файлы
mkdir -p wheels
pip download -r apps/api/requirements.txt -d wheels

# На целевой машине — установить из wheels
python -m venv .venv
source .venv/bin/activate   # или .venv\Scripts\activate.bat на Windows
pip install --no-index --find-links=./wheels -r apps/api/requirements.txt
```

Корпоративный PyPI-индекс:

```bash
export PIP_INDEX_URL=https://<your-corp-pypi>/simple
pip install -r apps/api/requirements.txt
```

---

## Зависимости (backend)

Файл `apps/api/requirements.txt`:

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `fastapi` | 0.115.4 | Web-фреймворк API |
| `uvicorn` | 0.32.0 | ASGI-сервер |
| `python-multipart` | 0.0.12 | Загрузка файлов (multipart) |
| `httpx` | 0.27.2 | HTTP-клиент |
| `numpy` | 2.1.3 | Численные вычисления |
| `langdetect` | 1.0.9 | Определение языка текста |
| `python-docx` | 1.1.2 | Парсинг DOCX |
| `openpyxl` | 3.1.5 | Парсинг XLSX |
| `PyMuPDF` | 1.24.11 | Парсинг PDF |
| `pytesseract` | 0.3.13 | OCR (опционально) |
| `opencv-python` | 4.10.0.84 | Обработка изображений |
| `tiktoken` | 0.8.0 | Токенизация текста |
| `sqlite-vec` | 0.1.6 | Векторный поиск в SQLite |
| `pytest` | 8.3.3 | Тестирование |

Frontend использует **Next.js 14**, **React 18**, **TanStack Query**, **Zod**.

---

## Типовые проблемы

| Проблема | Решение |
|----------|---------|
| `python` не найден | Переустановите Python с опцией «Add to PATH» |
| Ошибка активации `.venv` в PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `pip install` блокируется proxy | `PIP_INDEX_URL=https://<pypi>/simple pip install ...` |
| `npm install` даёт 403/timeout | `npm config set registry https://<corp-registry>/` |
| `next-swc.win32-x64-msvc.node is not a valid Win32 application` | Убедитесь, что Node.js 64-битный (`node -p "process.arch"` → `x64`). Удалите и переустановите: `Remove-Item -Recurse -Force node_modules, package-lock.json && npm install` |
| `npm install` падает без интернета | Настройте корпоративный npm registry или используйте offline npm cache |

---

## Структура проекта

```
RAG/
├── apps/
│   ├── api/               # FastAPI backend
│   │   ├── main.py                    # Точка входа FastAPI
│   │   ├── config.py                  # Константы и пути
│   │   ├── logging_setup.py           # Настройка логирования
│   │   ├── store.py                   # Реэкспорт синглтона store
│   │   ├── schemas/                   # Pydantic-контракты API
│   │   │   ├── __init__.py            # Реэкспорт всех схем
│   │   │   ├── notebooks.py           # Схемы ноутбуков
│   │   │   ├── sources.py             # Схемы источников
│   │   │   ├── chat.py                # Схемы чата и цитат
│   │   │   ├── notes.py               # Схемы заметок и сохранённых цитат
│   │   │   ├── llm.py                 # Схемы LLM-статуса
│   │   │   └── common.py              # Общие утилиты (now_iso)
│   │   ├── routers/                   # HTTP-роутеры (тонкий слой)
│   │   │   ├── notebooks.py           # CRUD ноутбуков
│   │   │   ├── sources.py             # Загрузка и индексация источников
│   │   │   ├── chat.py                # Чат и SSE-стриминг
│   │   │   ├── citations.py           # Сохранённые цитаты
│   │   │   ├── global_notes.py        # Глобальные заметки
│   │   │   ├── llm.py                 # Статус индексации
│   │   │   ├── client_events.py       # Клиентские события
│   │   │   └── agents.py              # Агентные запросы
│   │   ├── services/                  # Бизнес-логика
│   │   │   ├── state.py               # In-memory хранилище: структуры данных
│   │   │   ├── orchestrator.py        # Оркестрация индексации и сервисов
│   │   │   ├── prompts.py             # Системные промпты и сборка контекста
│   │   │   ├── model_chat.py          # Вызовы LLM (Ollama/OpenAI)
│   │   │   ├── search_service.py      # Гибридный поиск (vector + FTS + RRF)
│   │   │   ├── embedding_service.py   # Генерация эмбеддингов
│   │   │   ├── index_service.py       # Координация парсинга
│   │   │   ├── global_db.py           # SQLite: ноутбуки, источники, настройки
│   │   │   ├── chat_modes.py          # Режимы чата и пороги релевантности
│   │   │   ├── parse_service.py       # Реэкспорт модуля parse/
│   │   │   ├── parse/                 # Модуль парсинга документов
│   │   │   │   ├── models.py          # Типы данных: ChunkType, ParsedChunk и др.
│   │   │   │   ├── constants.py       # CHUNKING_METHODS, _HIERARCHY_PATTERNS
│   │   │   │   ├── utils.py           # Токенизация, подсчёт токенов
│   │   │   │   ├── serializer.py      # Сохранение/загрузка JSON чанков
│   │   │   │   ├── parser.py          # DocumentParser — оркестратор
│   │   │   │   ├── extractors/        # Стратегии извлечения текста по формату
│   │   │   │   │   ├── base.py        # ABC BaseExtractor
│   │   │   │   │   ├── text.py        # TXT, MD
│   │   │   │   │   ├── docx.py        # DOCX
│   │   │   │   │   ├── pdf.py         # PDF text-layer
│   │   │   │   │   └── ocr.py         # PDF OCR (pytesseract + opencv)
│   │   │   │   └── chunkers/          # Стратегии разбивки на чанки
│   │   │   │       ├── base.py        # ABC BaseChunker
│   │   │   │       ├── general.py     # GeneralChunker (базовый)
│   │   │   │       ├── context_enrichment.py  # Обогащение контекстом соседей
│   │   │   │       ├── hierarchy.py   # Иерархическое разбиение
│   │   │   │       ├── pcr.py         # Parent-Child Retrieval
│   │   │   │       └── symbol.py      # Разбиение по символу-разделителю
│   │   │   └── notebook_db/           # SQLite: чанки, эмбеддинги, поиск
│   │   │       ├── schema.py          # DDL и миграции
│   │   │       ├── documents.py       # CRUD документов
│   │   │       ├── search.py          # FTS и векторный поиск
│   │   │       └── db.py              # NotebookDB — оркестратор соединения
│   │   └── requirements.txt
│   └── web/               # Next.js frontend
│       ├── app/           # Страницы (notebooks list, notebook workspace)
│       ├── components/    # SourcesPanel, ChatPanel, EvidencePanel, DocPreview
│       ├── lib/           # api.ts (клиент), sse.ts (стриминг)
│       └── types/         # DTO-типы
├── agent/                 # Агентные компоненты
├── data/                  # Файловое хранилище (создаётся при запуске)
│   ├── docs/              # Загруженные файлы (<notebook_id>/...)
│   ├── notebooks/         # Индексы (SQLite и др.)
│   ├── parsing/           # JSON-артефакты чанков
│   └── logs/sessions/     # Лог-файлы
├── scripts/               # verify.sh, dev_run.sh
├── Makefile               # run-api, verify, smoke
├── launch.bat             # Лаунчер для Windows
└── .env.example           # Шаблон конфигурации frontend
```

---

## Рабочий процесс (от загрузки до ответа)

1. Пользователь загружает файл → `POST /api/notebooks/{id}/sources/upload`
2. Backend сохраняет файл в `data/docs/<notebook_id>/`
3. Фоновый поток индексации: извлечение текста → чанкинг → сохранение блоков
4. Статус источника переходит в `indexed` (или `failed`)
5. Пользователь задаёт вопрос → `GET /api/chat/stream`
6. Retrieval: токенизация запроса → ранжирование чанков → top-N citations
7. Ответ отдаётся потоком SSE: `token → citations → done`
8. Frontend отображает текст и панель доказательств

---

## Методы чанкинга

Конфигурируется через настройки источника. Доступно 5 методов:

- **Fixed size** — фрагменты фиксированного размера с overlap
- **Sentence-based** — разбиение по предложениям
- **Paragraph-based** — разбиение по абзацам
- **Section-based** — по обнаруженным заголовкам разделов
- **Semantic** — двухуровневый parent/child чанкинг с сохранением контекста

---

## Команды Make

```bash
make run-api   # Запустить API через scripts/dev_run.sh
make verify    # Полная проверка backend (compile + pytest + upload + indexing + SSE)
make smoke     # Псевдоним verify
```

---

## Быстрая проверка через curl

```bash
# Получить ID первого ноутбука
NB_ID=$(curl -s http://127.0.0.1:8000/api/notebooks | python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Загрузить тестовый файл
curl -s -X POST "http://127.0.0.1:8000/api/notebooks/$NB_ID/sources/upload" \
  -F "file=@/tmp/test.pdf;type=application/pdf"

# Отправить вопрос (SSE-стрим)
curl -N "http://127.0.0.1:8000/api/chat/stream?notebook_id=$NB_ID&message=summary&mode=qa"
```

---

## Руководство по интерфейсу

### Главная страница `/notebooks`

- **New notebook** — создание нового ноутбука
- Клик по карточке — открыть ноутбук
- Правая боковая панель — настройки подключения (`API URL`, провайдер, модель)

### Рабочее пространство ноутбука `/notebooks/[id]`

**Левая панель — Sources:**
- Загрузка файлов (PDF/DOCX/XLSX)
- Список источников с чекбоксами для выбора активных документов
- Двойной клик — открытие документа в превью
- Поиск по источникам, массовые операции

**Центральная панель — Chat:**
- Переключение режима: QA / Draft / Table / Summarize
- Переключение режима поиска: RAG strict / Model analytical
- Поле ввода + кнопка отправки
- Кнопки под ответом: `Copy`, `Save to Notes`

**Правая панель — Evidence:**
- Вкладка **Citations** — цитаты с привязкой к странице/разделу
- Вкладка **Notes** — сохранённые заметки
- Превью документа при клике по citation

Обе боковые панели поддерживают сворачивание и изменение ширины перетаскиванием разделителя.

---

## Логирование

Логи хранятся в `data/logs/sessions/`. При каждом запуске создаются два файла:

| Файл | Содержимое |
|------|-----------|
| `app_YYYY-MM-DD_HH-MM.log` | HTTP-запросы, индексация, ошибки сервера |
| `ui_YYYY-MM-DD_HH-MM.log` | Действия пользователя в интерфейсе |

Ротация происходит автоматически каждые **4 часа** (до 12 ротаций = 48 ч работы).

Просмотр через PowerShell:

```powershell
$f = Get-ChildItem data\logs\sessions\app_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $f.FullName -Wait -Tail 50
```
