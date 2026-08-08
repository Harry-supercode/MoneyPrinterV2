#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MPV2_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/cron.log"
LOCK_DIR="/tmp/moneyprinterv2-youtube-short.lock"
ACCOUNT_ID="${MPV2_YOUTUBE_ACCOUNT_ID:-}"
MODEL="${MPV2_OLLAMA_MODEL:-llama3.2:3b}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/snap/bin"
export DISPLAY="${DISPLAY:-:1}"
export PYTHONUNBUFFERED="1"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(timestamp)] SKIP youtube_short: previous run still active ($LOCK_DIR)" >> "$LOG"
  exit 75
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT" || {
  echo "[$(timestamp)] FAIL youtube_short: cannot cd to $ROOT" >> "$LOG"
  exit 1
}

if pgrep -f "[s]rc/cron.py youtube" >/dev/null 2>&1; then
  echo "[$(timestamp)] SKIP youtube_short: src/cron.py youtube already running" >> "$LOG"
  exit 75
fi

echo "[$(timestamp)] START youtube_short pid=$$" >> "$LOG"
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dimsu "$PYTHON" src/cron.py youtube "$ACCOUNT_ID" "$MODEL" >> "$LOG" 2>&1
else
  "$PYTHON" src/cron.py youtube "$ACCOUNT_ID" "$MODEL" >> "$LOG" 2>&1
fi
exit_code=$?
echo "[$(timestamp)] END youtube_short exit=$exit_code" >> "$LOG"
exit "$exit_code"
