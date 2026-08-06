#!/bin/zsh
set -u

ROOT="/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/random_scheduler.log"
LOCK_DIR="/tmp/moneyprinterv2-random-scheduler.lock"

export HOME="/Users/harrytrinhtvf"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED="1"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  "$PYTHON" -c "from pathlib import Path; from datetime import datetime; ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z'); p=Path('$LOG'); p.parent.mkdir(parents=True,exist_ok=True); p.open('a').write(f'[{ts}] SKIP random_scheduler: previous tick still active\n')" 2>/dev/null || true
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT" || {
  "$PYTHON" -c "from pathlib import Path; from datetime import datetime; ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z'); p=Path('$LOG'); p.parent.mkdir(parents=True,exist_ok=True); p.open('a').write(f'[{ts}] FAIL random_scheduler: cannot cd to $ROOT\n')" 2>/dev/null || true
  exit 1
}

"$PYTHON" scripts/random_scheduler.py
