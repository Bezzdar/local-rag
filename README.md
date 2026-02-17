# local-rag-assistant

Локальный NotebookLM-подобный ассистент в monorepo:

- `apps/api` — FastAPI backend (upload → index → retrieval → chat/stream)
- `apps/web` — Next.js frontend
- `packages/rag_core` — перенесённое legacy-ядро (`app/`, `parsers/`)

## Legacy core

В `packages/rag_core` перенесены legacy-модули:

- `packages/rag_core/app/*`
- `packages/rag_core/parsers/*`

Оригинальные `app/` и `parsers/` в корне сохранены.

## What is real vs mock

### Реально работает
- Upload сохраняет файл в `data/docs/<notebook_id>/...`.
- Source проходит `indexing -> indexed/failed`.
- `GET /api/notebooks/{id}/index/status` показывает реальные счётчики.
- `GET /api/chat/stream` делает retrieval по индексированным блокам и возвращает citations с метаданными (`filename`, `page`, `section`).

### Упрощено
- Legacy engine включается флагом `ENABLE_LEGACY_ENGINE=1` (по умолчанию off в этом окружении).
- Генерация финального текста ответа пока template-based.

## Data paths

- docs: `data/docs/`
- index: `data/index/`
- chunks artifacts: `data/chunks/`

---

## Полная инвентаризация проекта (актуализировано)

Ниже описана **фактическая структура репозитория**, роли модулей и рабочий процесс RAG-контура.

### 1) Карта репозитория

### Корневой уровень

- `README.md` — основной технический документ по архитектуре, запуску и верификации.
- `Makefile` — удобные алиасы (`run-api`, `verify`, `smoke`).
- `scripts/verify.sh` — end-to-end smoke/verification сценарий (компиляция, pytest, upload, indexing, SSE).
- `TODO.md`, `TEST_REPORT.md` — рабочие артефакты состояния проекта.
- `streamlit_app.py` + `app/`, `parsers/` — legacy Streamlit-контур (сохранён для обратной совместимости).
- `api/`, `web/` — legacy-копии backend/frontend (исторический слой; основной активный контур — в `apps/*`).
- `data/` — файловое хранилище документов и индексов.

### Основной runtime-контур (активный)

- `apps/api/` — FastAPI backend (основной API-контур):
  - `main.py` — сборка приложения, CORS, подключение роутеров, health endpoints.
  - `config.py` — пути к `data/*`, лимиты upload.
  - `schemas.py` — Pydantic-контракты API.
  - `store.py` — in-memory state + orchestrator индексации источников.
  - `routers/`:
    - `notebooks.py` — CRUD блокнотов и статус индексации.
    - `sources.py` — загрузка/регистрация источников и выдача файлов.
    - `chat.py` — chat/sse, формирование citations.
    - `notes.py` — заметки.
  - `services/`:
    - `parse_service.py` — нормализация парсинга + fallback-режимы.
    - `index_service.py` — сбор и хранение индексированных блоков, optional legacy indexing trigger.
    - `search_service.py` — retrieval по индексированным чанкам.
  - `tests/` — API smoke/integration тесты.

- `apps/web/` — Next.js frontend:
  - `app/notebooks/[id]/page.tsx` — основная рабочая зона (sources/chat/evidence).
  - `components/` — UI-панели (`SourcesPanel`, `ChatPanel`, `EvidencePanel`, `RuntimeSettings`, `DocPreview`).
  - `lib/api.ts` — клиент API + zod-валидация DTO.
  - `lib/sse.ts` — SSE-клиент поточного ответа.
  - `types/dto.ts` — типы фронтового контракта.

### Ядро обработки документов

- `packages/rag_core/` — вынесенное legacy-ядро обработки:
  - `parsers/text_extraction.py` — извлечение текста, секционирование, семантическое chunking API.
  - `parsers/preprocessing.py`, `parsers/ner_extraction.py` — вспомогательная предобработка/NER.
  - `app/engine.py` — pipeline индексации в Chroma.
  - `app/chunk_manager.py` — parent/child chunking, chunk storage helpers.
  - `app/search_tools.py` — TF-IDF + semantic rerank утилиты.
  - прочие модули (`search_engine.py`, `term_graph.py`, и т.д.) — расширения retrieval/аналитики.

### Данные и артефакты

- `data/docs/<notebook_id>/` — физические загруженные файлы.
- `data/index/` — persistent index storage (в т.ч. Chroma для legacy-контура).
- `data/chunks/` — JSON-артефакты чанков.

---

### 2) Сквозной рабочий процесс (от загрузки файла до ответа)

Ниже — **последовательность исполнения** для текущего активного контура `apps/api + apps/web`.

1. Пользователь загружает файл во frontend (`SourcesPanel`), фронт вызывает:
   - `POST /api/notebooks/{id}/sources/upload` (multipart).
2. Backend (`sources.py`) сохраняет файл в `data/docs/<notebook_id>/<uuid>-<filename>`.
3. `store.add_source_from_path(...)` создаёт `Source` со статусом `indexing` и запускает фоновой поток индексации.
4. Фоновая индексация вызывает `index_service.index_source(...)`:
   - выполняется `parse_service.extract_blocks(path)`;
   - блоки приводятся к унифицированному контракту (`source_id`, `page`, `section_id`, `section_title`, `text`, `type`);
   - блоки сохраняются в in-memory `INDEXED_BLOCKS[notebook_id]`.
5. После успеха статус источника переводится в `indexed` (или `failed` при ошибке).
6. Пользователь отправляет вопрос, frontend открывает `GET /api/chat/stream?...`.
7. `chat_stream` вызывает retrieval `search_service.search(...)`:
   - фильтрация по выбранным source ids;
   - ранжирование по текущему алгоритму;
   - top-N чанков преобразуются в citations.
8. Ответ формируется шаблонно (`_build_answer`) и отдаётся как SSE-события:
   - `token` (поток текста), затем `citations`, затем `done`.
9. Фронт отображает поток ответа, а справа — evidence/citations.

---

### 3) Последовательности парсинга и чанкинга

## 3.1 Активный API-путь (`apps/api/services/parse_service.py`)

Текущая боевая ветка ориентирована на устойчивость и предсказуемость:

1. Проверка расширения: поддерживаются `.pdf/.docx/.xlsx/.txt/.log/.doc`.
2. Для `.pdf/.docx/.xlsx` используется **быстрый fallback-блок** (placeholder extraction), чтобы не ломать ingest в окружениях без тяжёлых парсеров.
3. Для `.txt/.log/.doc` и прочих разрешённых вариантов — попытка полноценного `rag_core.parsers.text_extraction.extract_blocks`.
4. При исключении — fallback-блок с техническим описанием причины.

Результат: API всегда возвращает хотя бы один нормализованный блок и может завершить индексацию, даже в деградированном режиме.

## 3.2 Полный parser/chunking pipeline (`packages/rag_core/parsers/text_extraction.py`)

Когда используется полноценное извлечение, цепочка такая:

1. **Извлечение текста** по формату:
   - PDF: `PyMuPDF (fitz)`, постранично, параллельная выборка страниц.
   - DOCX/DOC: `python-docx`, включая таблицы (в markdown-подобное представление).
   - TXT/LOG: прямое чтение.
2. **Очистка текста**:
   - удаление непечатаемых символов,
   - нормализация пробелов/переносов.
3. **Удаление повторяющегося page-noise** (headers/footers):
   - линии, повторяющиеся на значимой доле страниц, вырезаются.
4. **Секционирование**:
   - эвристика заголовков (`1.2 ...`, `РАЗДЕЛ ...`, upper headings),
   - формируются пары `(section_title, section_text)` и `section_id` вида `p{page}.s{n}`.
5. Опционально: **TextRank boundaries** (sumy), если включён режим `use_textrank`.

## 3.3 Семантический чанкинг (`packages/rag_core/app/chunk_manager.py`)

Для legacy-индексации в Chroma используется двухуровневое дробление:

1. Внутри блока: `_split_technical_sections(...)` по техзаголовкам.
2. Формируются **parent chunks** (крупные контекстные окна, `_PARENT_MAX_LEN`).
3. Для каждого parent формируются **child chunks** (`_CHILD_MAX_LEN`) с overlap по предложениям.
4. Между child и parent сохраняется связь через `parent_id`.

Это даёт компромисс между полнотой контекста (parent) и точностью retrieval (child).

---

### 4) Какие алгоритмы используются

В проекте одновременно присутствуют алгоритмы **активного** и **legacy** контура.

### Активный контур (`apps/api`)

- Retrieval ранжирование: упрощённый keyword-подход
  - токенизация регуляркой (`[\w\-]+`),
  - базовая AND-группа,
  - fallback сортировка по наличию подстроки + длине чанка.
- Генерация ответа: template-based (без LLM-генерации по умолчанию).
- Стриминг: SSE (`token -> citations -> done`).

### Legacy / расширенный контур (`packages/rag_core`)

- TF-IDF retrieval (`sklearn` cosine similarity).
- Semantic rerank через `SentenceTransformer` эмбеддинги (cosine в embedding space).
- Simhash near-duplicate filtering при chunking.
- Adaptive chunk sizing по средней длине предложения.
- TextRank для выделения смысловых границ (при наличии sumy).
- Индексация в Chroma с метаданными (`file_path`, `page_label`, `section_id`, `term_tags`, `parent_id`).

---

### 5) Роли ключевых файлов (быстрый справочник)

- `apps/api/store.py` — единая точка управления жизненным циклом notebook/source/message/note и фоновой индексацией.
- `apps/api/services/index_service.py` — конвертация parser blocks в индексируемые блоки notebook-level.
- `apps/api/services/search_service.py` — retrieval + преобразование chunk -> citation fields.
- `packages/rag_core/parsers/text_extraction.py` — «источник истины» по извлечению/нормализации/секции текста.
- `packages/rag_core/app/chunk_manager.py` — управляет структурным семантическим чанкингом (parent/child).
- `packages/rag_core/app/engine.py` — end-to-end legacy индексатор (extract -> chunk -> embed -> chroma).
- `apps/web/app/notebooks/[id]/page.tsx` — orchestration UI workflow (queries/mutations/SSE).
- `apps/web/lib/api.ts`, `apps/web/lib/sse.ts` — transport слой frontend.

---

## Установка и запуск на Windows (рекомендуемый сценарий)

Ниже — основной путь развёртывания под Windows 10/11, т.к. проект в первую очередь ориентирован на эту ОС.

### 1) Требования

- **Python 3.10+** (рекомендуется 3.11), установленный с опцией `Add python.exe to PATH`.
- **Node.js 20 LTS** (для `apps/web`).
- **Git for Windows**.
- **Microsoft Visual C++ Redistributable 2015-2022** (часто нужен для Python-пакетов).

Проверка в `PowerShell`:

```powershell
python --version
pip --version
node --version
npm --version
git --version
```

### 2) Клонирование репозитория

```powershell
git clone <URL_ВАШЕГО_РЕПО>
cd RAG
```

### 3) Настройка backend (FastAPI) на Windows

#### Вариант A (рекомендуется, вручную через `.venv`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r apps/api/requirements.txt
```

Если PowerShell блокирует активацию скриптов:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

#### Вариант B (legacy, через `.bat`-скрипт)

Для Streamlit-сценария в корне есть автоматизация:

```bat
setup_venv.bat
start_app.bat
```

> Этот путь использует `requirements.txt` в корне и запускает `streamlit_app.py`.

### 4) Запуск backend API

Из корня репозитория (с активированным `.venv`):

```powershell
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверка, что API поднялся:

- Swagger UI: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/api/health

### 5) Настройка и запуск frontend (Next.js)

Откройте **второй** терминал в корне репозитория:

```powershell
cd apps/web
npm install
Copy-Item ..\..\.env.example .env.local
npm run dev
```

После запуска web обычно доступен на:

- http://localhost:3000

### 6) Быстрая проверка после запуска

1. Откройте web-интерфейс.
2. Создайте/выберите notebook.
3. Загрузите PDF/DOCX/XLSX.
4. Дождитесь статуса `indexed`.
5. Отправьте вопрос в чат и проверьте citations справа.

### 7) Типовые проблемы на Windows

- **`python` не найден**
  - Переустановите Python с опцией `Add to PATH`.
- **Ошибка активации `.venv` в PowerShell**
  - Используйте `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- **`npm install` даёт 403/timeout в корпоративной сети**
  - Пропишите внутренний registry:
    ```powershell
    npm config set registry https://<your-corp-npm-registry>/
    ```
- **`pip install` блокируется proxy/403**
  - Используйте корпоративный PyPI (`PIP_INDEX_URL`) или офлайн-колёса (см. раздел ниже).

---

## Quick Start (API)

### Online install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
```

### Offline install (wheels)

```bash
# online machine
mkdir -p wheels
pip download -r apps/api/requirements.txt -d wheels

# offline machine
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links=./wheels -r apps/api/requirements.txt
```

Для корпоративного индекса:

```bash
export PIP_INDEX_URL=https://<your-corp-pypi>/simple
pip install -r apps/api/requirements.txt
```

### Run API

```bash
make run-api
# или
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Full verification (проверено)

```bash
make verify
# или
bash scripts/verify.sh
```

---

## Quick Start (Web)

```bash
cd apps/web
npm install
cp ../../.env.example .env.local
npm run dev
```

### Статус в текущем окружении

В этом окружении `npm` registry недоступен:

- `npm install` падает с `E403 Forbidden`.
- `npm run build` не стартует без зависимостей (`next: not found`).

### Альтернативы

1. Настроить корпоративный registry/proxy:

```bash
npm config set registry https://<your-corp-npm-registry>/
```

2. Offline установка из локального кэша/tarball (prebuilt node_modules cache/mirror).

---

## Manual testing checklist

1. **Upload**: загрузить PDF/DOCX/XLSX в выбранный notebook.
2. **Index**: проверить, что статусы source переходят в `indexed`.
3. **Chat**: отправить вопрос в чат (`mode=qa`).
4. **Citations**: убедиться, что справа есть citations с `filename` и `page/section`.

---

## Smoke checks (manual curl)

```bash
NB_ID=$(curl -s http://127.0.0.1:8000/api/notebooks | python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

echo 'sample-pdf' > /tmp/smoke.pdf
curl -s -X POST "http://127.0.0.1:8000/api/notebooks/$NB_ID/sources/upload" \
  -F "file=@/tmp/smoke.pdf;type=application/pdf"

SRC_JSON=$(curl -s "http://127.0.0.1:8000/api/notebooks/$NB_ID/sources")
FILE_PATH=$(echo "$SRC_JSON" | python -c "import sys,json; print(json.load(sys.stdin)[-1]['file_path'])")

curl -sG "http://127.0.0.1:8000/api/files" \
  --data-urlencode "path=$FILE_PATH" -o /tmp/downloaded.bin

curl -N "http://127.0.0.1:8000/api/chat/stream?notebook_id=$NB_ID&message=section&mode=qa"
```

---

## Make commands

```bash
make verify   # full backend verification pipeline
make run-api  # start API with logs via scripts/dev_run.sh
make smoke    # alias to verify
```

---

## Known issues

- `pip install` может быть заблокирован proxy/403.
  - workaround: wheels (`pip download` + `--no-index --find-links`).
- `npm install` может быть заблокирован registry/403.
  - workaround: корпоративный registry/proxy или offline npm cache.

---

## Deployment note (manual)

Перед ручным развёртыванием на новом окружении:

1. `make verify`
2. Проверить `TEST_REPORT.md`
3. Если web блокирован по npm — сначала поднять внутренний registry/proxy
