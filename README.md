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
