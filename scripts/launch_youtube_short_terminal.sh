#!/bin/zsh
set -u

SCRIPT_DIR="${0:A:h}"
RUNNER="$SCRIPT_DIR/run_youtube_short_job.sh"
LAUNCH_LOG="$SCRIPT_DIR/youtube_short_launcher.log"
UPLOAD_TIKTOK="${MPV2_UPLOAD_TIKTOK:-1}"
UPLOAD_FACEBOOK_REELS="${MPV2_UPLOAD_FACEBOOK_REELS:-1}"
COMMAND="MPV2_UPLOAD_TIKTOK='$UPLOAD_TIKTOK' MPV2_UPLOAD_FACEBOOK_REELS='$UPLOAD_FACEBOOK_REELS' /bin/zsh '$RUNNER'"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

echo "[$(timestamp)] ATTEMPT youtube_short launcher" >> "$LAUNCH_LOG"

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
  echo "[$(timestamp)] STARTED youtube_short Terminal session: $output" >> "$LAUNCH_LOG"
else
  exit_code=$?
  echo "[$(timestamp)] FAIL youtube_short launcher exit=$exit_code: $output" >> "$LAUNCH_LOG"
  exit "$exit_code"
fi
