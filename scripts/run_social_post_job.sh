#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MPV2_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/social_posts.log"
LOCK_DIR="/tmp/moneyprinterv2-social-post.lock"
PLATFORM="${MPV2_SOCIAL_POST_PLATFORM:-all}"
MODEL="${MPV2_OLLAMA_MODEL:-llama3.2:3b}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/snap/bin"
export DISPLAY="${DISPLAY:-:1}"
export PYTHONUNBUFFERED="1"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(timestamp)] SKIP social_post: previous run still active ($LOCK_DIR)" >> "$LOG"
  exit 75
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT" || {
  echo "[$(timestamp)] FAIL social_post: cannot cd to $ROOT" >> "$LOG"
  exit 1
}

if pgrep -f "[s]rc/social_post_cron.py" >/dev/null 2>&1; then
  echo "[$(timestamp)] SKIP social_post: src/social_post_cron.py already running" >> "$LOG"
  exit 75
fi

if [ -d "/tmp/moneyprinterv2-youtube-short.lock" ] || [ -d "/tmp/moneyprinterv2-dub-pipeline.lock" ]; then
  echo "[$(timestamp)] SKIP social_post: video/dub lock exists" >> "$LOG"
  exit 75
fi

if pgrep -f "[s]rc/cron.py youtube|[s]rc/dub_cron.py" >/dev/null 2>&1; then
  echo "[$(timestamp)] SKIP social_post: video/dub job already running" >> "$LOG"
  exit 75
fi

echo "[$(timestamp)] START social_post pid=$$ platform=$PLATFORM" >> "$LOG"
"$PYTHON" src/social_post_cron.py --platform "$PLATFORM" --model "$MODEL" >> "$LOG" 2>&1
exit_code=$?
echo "[$(timestamp)] END social_post exit=$exit_code" >> "$LOG"
exit "$exit_code"
