#!/bin/zsh
set -u

SCRIPT_DIR="${0:A:h}"
RUNNER="$SCRIPT_DIR/run_random_scheduler.sh"
SUPPORT_DIR="$HOME/Library/Application Support/MoneyPrinterV2"
LAUNCH_LOG="$SUPPORT_DIR/random_scheduler_launcher.log"
COMMAND="/bin/zsh '$RUNNER'"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S %Z"
}

mkdir -p "$SUPPORT_DIR"
echo "[$(timestamp)] ATTEMPT random_scheduler launcher" >> "$LAUNCH_LOG"

if output=$(/usr/bin/osascript 2>&1 <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "$COMMAND"
end tell
APPLESCRIPT
); then
  echo "[$(timestamp)] STARTED random_scheduler Terminal session: $output" >> "$LAUNCH_LOG"
else
  exit_code=$?
  echo "[$(timestamp)] FAIL random_scheduler launcher exit=$exit_code: $output" >> "$LAUNCH_LOG"
  exit "$exit_code"
fi
