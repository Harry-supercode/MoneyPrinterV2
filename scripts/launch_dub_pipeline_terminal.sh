#!/bin/zsh
set -u

SCRIPT_DIR="${0:A:h}"
RUNNER="$SCRIPT_DIR/run_dub_pipeline_job.sh"
LAUNCH_LOG="$SCRIPT_DIR/dub_launcher.log"
UPLOAD_YOUTUBE="${MPV2_DUB_UPLOAD_YOUTUBE:-1}"
UPLOAD_TIKTOK="${MPV2_DUB_UPLOAD_TIKTOK:-0}"
UPLOAD_FACEBOOK_REELS="${MPV2_DUB_UPLOAD_FACEBOOK_REELS:-1}"
COMMAND="MPV2_DUB_UPLOAD_YOUTUBE='$UPLOAD_YOUTUBE' MPV2_DUB_UPLOAD_TIKTOK='$UPLOAD_TIKTOK' MPV2_DUB_UPLOAD_FACEBOOK_REELS='$UPLOAD_FACEBOOK_REELS' /bin/zsh '$RUNNER'"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

echo "[$(timestamp)] ATTEMPT dub_pipeline launcher" >> "$LAUNCH_LOG"

if output=$(/usr/bin/osascript - "$COMMAND" 2>&1 <<'APPLESCRIPT'
on run argv
  set launchCommand to item 1 of argv
  ignoring application responses
    tell application "Terminal"
      activate
      do script launchCommand
    end tell
  end ignoring
  return "scheduled"
end run
APPLESCRIPT
); then
  echo "[$(timestamp)] STARTED dub_pipeline Terminal session: $output" >> "$LAUNCH_LOG"
else
  exit_code=$?
  echo "[$(timestamp)] FAIL dub_pipeline launcher exit=$exit_code: $output" >> "$LAUNCH_LOG"
  exit "$exit_code"
fi
