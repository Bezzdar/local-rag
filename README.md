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

