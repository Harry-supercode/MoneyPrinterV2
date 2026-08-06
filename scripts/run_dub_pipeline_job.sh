#!/bin/zsh
set -u

ROOT="/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/dub_cron.log"
LOCK_DIR="/tmp/moneyprinterv2-dub-pipeline.lock"

export HOME="/Users/harrytrinhtvf"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
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
/usr/bin/caffeinate -dimsu "$PYTHON" src/dub_cron.py "" llama3.2:latest >> "$LOG" 2>&1
exit_code=$?
echo "[$(timestamp)] END dub_pipeline exit=$exit_code" >> "$LOG"
exit "$exit_code"
