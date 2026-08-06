#!/bin/zsh
set -u

ROOT="/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/cron.log"
LOCK_DIR="/tmp/moneyprinterv2-youtube-short.lock"

export HOME="/Users/harrytrinhtvf"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
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
/usr/bin/caffeinate -dimsu "$PYTHON" src/cron.py youtube 2e7b83ef-4608-4ba8-a7b5-3a56be6c102a llama3.2:latest >> "$LOG" 2>&1
exit_code=$?
echo "[$(timestamp)] END youtube_short exit=$exit_code" >> "$LOG"
exit "$exit_code"
