#!/bin/zsh
# Sends the Shopee login-reminder email with this week's brand list.
# Standalone reminder sender. The scheduled path is run_weekly.sh, which sends
# this same reminder only when its preflight finds the session expired.

PROJECT_DIR="/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot"
PYTHON="/opt/homebrew/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d)"

cd "$PROJECT_DIR" || exit 1
echo "===== Reminder started: $(date) =====" >> "$LOG_DIR/reminder_$STAMP.log"
"$PYTHON" -c "from read_brands_from_sheet import fetch_bottom_brands; from send_email import send_login_reminder; send_login_reminder(fetch_bottom_brands())" >> "$LOG_DIR/reminder_$STAMP.log" 2>&1
echo "===== Reminder finished: $(date) (exit $?) =====" >> "$LOG_DIR/reminder_$STAMP.log"
