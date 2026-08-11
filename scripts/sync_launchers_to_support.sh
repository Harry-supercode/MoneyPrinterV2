#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPPORT_DIR="$HOME/Library/Application Support/MoneyPrinterV2"

mkdir -p "$SUPPORT_DIR"

copy_script() {
  local src="$1"
  local dst_name="$2"
  local dst="$SUPPORT_DIR/$dst_name"

  if [[ ! -f "$src" ]]; then
    echo "[sync] WARN missing source script: $src"
    return 1
  fi

  cp "$src" "$dst"
  chmod +x "$dst"
  echo "[sync] synced $dst_name"
}

copy_script "$ROOT_DIR/scripts/run_youtube_short_job.sh" "run_youtube_short_job.sh"
copy_script "$ROOT_DIR/scripts/run_dub_pipeline_job.sh" "run_dub_pipeline_job.sh"
copy_script "$ROOT_DIR/scripts/run_social_post_job.sh" "run_social_post_job.sh"
copy_script "$ROOT_DIR/scripts/run_random_scheduler.sh" "run_random_scheduler.sh"

copy_script "$ROOT_DIR/scripts/launch_youtube_short_terminal.sh" "launch_youtube_short_terminal.sh"
copy_script "$ROOT_DIR/scripts/launch_dub_pipeline_terminal.sh" "launch_dub_pipeline_terminal.sh"
copy_script "$ROOT_DIR/scripts/launch_random_scheduler_terminal.sh" "launch_random_scheduler_terminal.sh"

echo "[sync] done: $SUPPORT_DIR"
