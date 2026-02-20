#!/usr/bin/env bash
# Скрипт локального запуска backend API (uvicorn) с логированием в файл.
set -euo pipefail

# --- Подготовка путей и лог-файла ---
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p .logs
LOG_FILE=".logs/api-$(date +%Y%m%d-%H%M%S).log"

echo "[dev_run] starting uvicorn..."
echo "[dev_run] log: $LOG_FILE"

touch "$LOG_FILE"
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload >>"$LOG_FILE" 2>&1 &
PID=$!

echo "[dev_run] pid=$PID"
echo "[dev_run] press Ctrl+C to stop"

# --- Корректная остановка фонового процесса ---
cleanup() {
  echo "[dev_run] stopping uvicorn pid=$PID"
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

tail -f "$LOG_FILE"
