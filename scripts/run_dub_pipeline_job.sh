#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MPV2_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/dub_cron.log"
LOCK_DIR="/tmp/moneyprinterv2-dub-pipeline.lock"
ACCOUNT_ID="${MPV2_DUB_ACCOUNT_ID:-}"
MODEL="${MPV2_OLLAMA_MODEL:-llama3.2:3b}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/snap/bin"
export DISPLAY="${DISPLAY:-:1}"
export PYTHONUNBUFFERED="1"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(timestamp)] SKIP dub_pipeline: previous run still active ($LOCK_DIR)" >> "$LOG"
  exit 75
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT" || {
  echo "[$(timestamp)] FAIL dub_pipeline: cannot cd to $ROOT" >> "$LOG"
  exit 1
}

if pgrep -f "[s]rc/dub_cron.py" >/dev/null 2>&1; then
  echo "[$(timestamp)] SKIP dub_pipeline: src/dub_cron.py already running" >> "$LOG"
  exit 75
fi

echo "[$(timestamp)] START dub_pipeline pid=$$" >> "$LOG"
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dimsu "$PYTHON" src/dub_cron.py "$ACCOUNT_ID" "$MODEL" >> "$LOG" 2>&1
else
  "$PYTHON" src/dub_cron.py "$ACCOUNT_ID" "$MODEL" >> "$LOG" 2>&1
fi
exit_code=$?
echo "[$(timestamp)] END dub_pipeline exit=$exit_code" >> "$LOG"
exit "$exit_code"
