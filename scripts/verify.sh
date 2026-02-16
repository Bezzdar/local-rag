#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="http://127.0.0.1:8000"
TMP_DIR="$(mktemp -d)"
UVICORN_PID=""
NOTEBOOK_IDS=()

log() { echo "[verify] $*"; }

sha256_file() {
  python - "$1" <<'PY'
import hashlib,sys
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
    while True:
        b=f.read(1024*1024)
        if not b:
            break
        h.update(b)
print(h.hexdigest())
PY
}

wait_api() {
  python - <<'PY'
import time,urllib.request
url='http://127.0.0.1:8000/health'
for _ in range(80):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            if r.status==200:
                raise SystemExit(0)
    except Exception:
        time.sleep(0.2)
raise SystemExit('API did not start in time')
PY
}

cleanup_notebooks() {
  for nb in "${NOTEBOOK_IDS[@]:-}"; do
    [[ -z "$nb" ]] && continue
    curl -sS -X DELETE "$API_URL/api/notebooks/$nb" >/dev/null || true
    rm -rf "data/docs/$nb" || true
  done
}

cleanup() {
  cleanup_notebooks
  if [[ -n "${UVICORN_PID}" ]] && kill -0 "${UVICORN_PID}" 2>/dev/null; then
    kill "${UVICORN_PID}" || true
    wait "${UVICORN_PID}" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log "1) compileall"
python -m compileall apps/api packages/rag_core

log "2) pytest"
pytest -q apps/api/tests

log "3) start uvicorn"
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 >"$TMP_DIR/uvicorn.log" 2>&1 &
UVICORN_PID=$!
wait_api

log "4) create notebook for smoke"
NB_JSON="$TMP_DIR/notebook.json"
curl -fsS -X POST "$API_URL/api/notebooks" -H "Content-Type: application/json" -d '{"title":"verify-smoke"}' > "$NB_JSON"
NOTEBOOK_ID="$(python - <<PY
import json
print(json.load(open('$NB_JSON'))['id'])
PY
)"
NOTEBOOK_IDS+=("$NOTEBOOK_ID")
log "using notebook: $NOTEBOOK_ID"

log "5) upload files"
PDF_FILE="$TMP_DIR/sample.pdf"
DOCX_FILE="$TMP_DIR/sample.docx"
XLSX_FILE="$TMP_DIR/sample.xlsx"
printf '%s' '%PDF-1.4 verify pdf sample' > "$PDF_FILE"
printf '%s' 'PK\x03\x04verify-docx' > "$DOCX_FILE"
printf '%s' 'PK\x03\x04verify-xlsx' > "$XLSX_FILE"

for item in "pdf:$PDF_FILE:application/pdf" "docx:$DOCX_FILE:application/vnd.openxmlformats-officedocument.wordprocessingml.document" "xlsx:$XLSX_FILE:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"; do
  IFS=':' read -r ext path ctype <<< "$item"
  out="$TMP_DIR/upload-$ext.json"
  curl -fsS -X POST "$API_URL/api/notebooks/$NOTEBOOK_ID/sources/upload" -F "file=@${path};type=${ctype}" > "$out"
  python - <<PY
import json
obj=json.load(open('$out'))
assert obj['id'] and obj['file_path'] and obj['filename']
PY
done

log "6) wait indexed"
python - <<PY
import json,time,urllib.request
nb='$NOTEBOOK_ID'
url=f'http://127.0.0.1:8000/api/notebooks/{nb}/sources'
end=time.time()+30
while time.time()<end:
    with urllib.request.urlopen(url, timeout=4) as r:
        data=json.load(r)
    latest=data[-3:] if len(data)>=3 else data
    if latest and all(s.get('status')=='indexed' for s in latest):
        raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit('Timed out waiting for indexed status')
PY

log "7) download + sha256"
for ext in pdf docx xlsx; do
  up_json="$TMP_DIR/upload-$ext.json"
  src_path="$(python - <<PY
import json
print(json.load(open('$up_json'))['file_path'])
PY
)"
  dst="$TMP_DIR/dl-$ext.bin"
  curl -fsS -G "$API_URL/api/files" --data-urlencode "path=$src_path" -o "$dst"
  src_orig="$TMP_DIR/sample.$ext"
  sha_src="$(sha256_file "$src_orig")"
  sha_dst="$(sha256_file "$dst")"
  [[ "$sha_src" == "$sha_dst" ]] || { echo "sha mismatch for $ext"; exit 1; }
done

log "8) SSE order and citations"
SSE_OUT="$TMP_DIR/sse.txt"
curl -fsS "$API_URL/api/chat/stream?notebook_id=$NOTEBOOK_ID&message=verify+section&mode=qa" > "$SSE_OUT"
python - <<PY
import json
text=open('$SSE_OUT',encoding='utf-8').read()
assert text.count('event: token') >= 1, 'no token events'
idx_token=text.find('event: token')
idx_cit=text.find('event: citations')
idx_done=text.find('event: done')
assert idx_token!=-1 and idx_cit!=-1 and idx_done!=-1, 'missing events'
assert idx_token < idx_cit < idx_done, 'invalid event order'
start=text.find('event: citations\ndata: ')
assert start!=-1
start += len('event: citations\ndata: ')
end=text.find('\n\n', start)
cit=json.loads(text[start:end])
assert isinstance(cit,list) and len(cit) >= 1, 'empty citations'
for c in cit:
    assert c.get('filename'), 'citation without filename'
PY

log "9) deterministic fallback mode check"
kill "$UVICORN_PID" || true
wait "$UVICORN_PID" 2>/dev/null || true
UVICORN_PID=""

FORCE_FALLBACK_MULTIPART=1 uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 >"$TMP_DIR/uvicorn-fallback.log" 2>&1 &
UVICORN_PID=$!
wait_api

NB_JSON2="$TMP_DIR/notebook2.json"
curl -fsS -X POST "$API_URL/api/notebooks" -H "Content-Type: application/json" -d '{"title":"verify-fallback"}' > "$NB_JSON2"
NOTEBOOK_ID2="$(python - <<PY
import json
print(json.load(open('$NB_JSON2'))['id'])
PY
)"
NOTEBOOK_IDS+=("$NOTEBOOK_ID2")

FALLBACK_FILE="$TMP_DIR/fallback.pdf"
printf '%s' '%PDF-1.4 fallback verify' > "$FALLBACK_FILE"
curl -fsS -X POST "$API_URL/api/notebooks/$NOTEBOOK_ID2/sources/upload" -F "file=@${FALLBACK_FILE};type=application/pdf" > "$TMP_DIR/fallback-upload.json"
python - <<PY
import json,time,urllib.request
source=json.load(open('$TMP_DIR/fallback-upload.json'))
assert source['id']
url=f"http://127.0.0.1:8000/api/notebooks/{source['notebook_id']}/sources"
end=time.time()+20
while time.time()<end:
    with urllib.request.urlopen(url, timeout=4) as r:
        items=json.load(r)
    cur=[x for x in items if x['id']==source['id']]
    if cur and cur[0]['status']=='indexed':
        raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit('fallback upload did not reach indexed')
PY

log "verify complete: SUCCESS"
