#!/bin/zsh
# Weekly Thursday runner for the Bottom Account bot.
#
# Invoked by the com.aha.bottom-account LaunchAgent, which fires every 15
# minutes from 07:30 to 09:00 on Thursdays. Each tick is cheap and idempotent:
#
#   * already ran successfully today   -> exit immediately
#   * another tick still running       -> exit immediately
#   * Shopee session expired           -> email the login reminder (once), exit
#   * session alive                    -> full run, then stop retrying
#
# So the user only has to log in when they see the reminder; the next tick
# picks it up on its own. The run takes over the mouse for ~an hour — don't
# touch the Mac once it starts (slam the pointer into a screen corner to abort).

PROJECT_DIR="/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot"
PYTHON="/opt/homebrew/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
STATE_DIR="$PROJECT_DIR/logs/state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

STAMP="$(date +%Y%m%d)"
LOG="$LOG_DIR/weekly_$STAMP.log"
DONE_MARKER="$STATE_DIR/done_$STAMP"
REMINDED_MARKER="$STATE_DIR/reminded_$STAMP"
LOCK="$STATE_DIR/run.lock"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

# python3 is invoked with -u throughout: with stdout redirected to a file Python
# block-buffers, so a run in progress shows an EMPTY log for minutes at a time.
# For an unattended hour-long job that makes "still working" and "hung" look
# identical. -u makes the log live.

cd "$PROJECT_DIR" || exit 1

# --- already done today? -----------------------------------------------------
if [ -f "$DONE_MARKER" ]; then
    exit 0
fi

# --- another tick still running? ---------------------------------------------
# mkdir is atomic, so this is a real mutex rather than a check-then-write race.
if ! mkdir "$LOCK" 2>/dev/null; then
    log "tick skipped — a run is already in progress"
    exit 0
fi
cleanup() { rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT INT TERM

log "===== tick ====="

# --- is the session alive? ---------------------------------------------------
"$PYTHON" -u preflight.py >> "$LOG" 2>&1
PRE=$?

if [ $PRE -eq 2 ]; then
    log "preflight error (Chrome unavailable) — will retry next tick"
    exit 0
fi

if [ $PRE -eq 1 ]; then
    if [ -f "$REMINDED_MARKER" ]; then
        log "still not logged in — reminder already sent, waiting"
    else
        log "not logged in — sending login reminder"
        "$PYTHON" -c "from read_brands_from_sheet import fetch_bottom_brands; from send_email import send_login_reminder; send_login_reminder(fetch_bottom_brands())" >> "$LOG" 2>&1 \
            && touch "$REMINDED_MARKER" \
            || log "WARNING: reminder email failed"
    fi
    exit 0
fi

# --- session alive: full run -------------------------------------------------
log "session alive — starting full run"

# Refresh the akun -> username mapping BEFORE reading the week's list. The Bottom
# sheet only carries akun codes (column C), so a brand whose username changed, or
# a brand added since the last sync, would otherwise be unsearchable or skipped.
# The sync only ADDS and reports; it never overwrites a username conflict, so a
# verified csv value cannot be clobbered by a stale sheet entry.
log "syncing akun -> username mapping from the Monitored Stores sheet"
"$PYTHON" -u sync_brands_from_sheet.py >> "$LOG" 2>&1 \
    || log "WARNING: brand mapping sync failed — continuing with the existing brands.csv"

# The brand list ALWAYS comes from the "Bottom" tab of the Google Sheet, which
# is refreshed every Thursday. brands.csv is NOT the source of the list — it
# only maps akun -> Shopee username, which the bot needs to search for a shop.
# A sheet brand with no mapping cannot be run, so it is reported loudly on its
# own line rather than silently dropped by the filter.
SHEET_OUT=$("$PYTHON" - <<'PYEOF' 2>>"$LOG"
import csv
from read_brands_from_sheet import fetch_bottom_brands
mapped = set()
with open("brands.csv") as f:
    for row in csv.DictReader(f):
        mapped.add(row["akun"].strip())
sheet = fetch_bottom_brands()
print("RUNNABLE " + " ".join(b for b in sheet if b in mapped))
print("MISSING " + " ".join(b for b in sheet if b not in mapped))
PYEOF
)
BRANDS=$(echo "$SHEET_OUT" | grep '^RUNNABLE ' | cut -d' ' -f2-)
MISSING=$(echo "$SHEET_OUT" | grep '^MISSING ' | cut -d' ' -f2-)

if [ -n "$MISSING" ]; then
    log "⚠ IN THE SHEET BUT NOT IN brands.csv (skipped, no username mapping): $MISSING"
    log "  → fix with: $PYTHON sync_brands_from_sheet.py, then re-run by hand"
fi

if [ -z "$BRANDS" ]; then
    log "no brands in the sheet matched brands.csv — nothing to do; marking done"
    touch "$DONE_MARKER"
    exit 0
fi

log "brands: $BRANDS"

"$PYTHON" -u shopee_ads_screenshot.py ${=BRANDS} >> "$LOG" 2>&1
SHOT_RC=$?
log "screenshot step exit $SHOT_RC"

if [ $SHOT_RC -ne 0 ]; then
    log "screenshots failed — NOT inserting into Slides. Marking done so the"
    log "retry loop stops; re-run by hand with run_bottom.command once fixed."
    "$PYTHON" -u report_run.py --log "$LOG" --brands "$BRANDS" \
        --shot-rc $SHOT_RC --slides-rc 1 >> "$LOG" 2>&1 \
        || log "WARNING: could not send the failure report"
    touch "$DONE_MARKER"
    exit $SHOT_RC
fi

"$PYTHON" -u insert_to_slides.py ${=BRANDS} >> "$LOG" 2>&1
INS_RC=$?
log "slides step exit $INS_RC"

# Report the outcome per brand. Until 2026-09-21 nothing here sent a result
# email at all, so a completed run — or a half-failed one — finished silently.
# report_run.py reads the status back from the log and from the files on disk
# rather than assuming success, and names the brands needing a manual redo.
"$PYTHON" -u report_run.py --log "$LOG" --brands "$BRANDS" \
    --shot-rc $SHOT_RC --slides-rc $INS_RC >> "$LOG" 2>&1 \
    || log "WARNING: could not send the run report"

touch "$DONE_MARKER"
log "===== run complete (screenshots $SHOT_RC, slides $INS_RC) ====="
exit $INS_RC
