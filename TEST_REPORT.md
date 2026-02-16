# TEST_REPORT

- Date: 2026-02-16 23:26:17 UTC
- Commit under test: `d9118de` (base before final stabilization commit)
- Environment:
  - OS: `Linux-6.12.47-x86_64-with-glibc2.39`
  - Python: `3.10.19`

## Results

### 1) compileall
- Command: `python -m compileall apps/api packages/rag_core`
- Result: ✅ PASS

### 2) pytest
- Command: `pytest -q apps/api/tests`
- Result: ✅ PASS (`5 passed`)

### 3) verify script
- Command: `bash scripts/verify.sh` / `make verify`
- Result: ✅ PASS
- Duration: `~51s`
- Covered checks:
  - compileall + pytest
  - uvicorn smoke run
  - upload `pdf/docx/xlsx`
  - poll indexed
  - download + sha256 compare
  - SSE order `token -> citations -> done`
  - non-empty citations with metadata
  - fallback mode `FORCE_FALLBACK_MULTIPART=1`

### 4) make commands
- Command: `make smoke`
- Result: ✅ PASS
- Command: `make run-api`
- Result: ✅ PASS (smoke-validated with timeout start/stop)

### 5) web build
- Command: `cd apps/web && npm install`
- Result: ❌ FAIL — Blocked by environment (`E403 Forbidden`, npm registry)

- Command: `cd apps/web && npm run build`
- Result: ❌ FAIL — `next: not found` (dependencies not installed because npm install blocked)

## Blocked by environment

- npm registry access unavailable in this environment (`403 Forbidden`).
- Web install/build cannot be fully validated until registry/proxy is available.

## Notes for tomorrow deployment

1. Run `make verify` first on target host.
2. If npm is blocked, configure internal npm registry/proxy or restore offline npm cache.
3. Re-run `cd apps/web && npm install && npm run build` after registry fix.
