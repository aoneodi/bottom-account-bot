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

# --- does python still hold its macOS permissions? -------------------------
# A Homebrew python upgrade silently drops them (2026-11-05: the whole Thursday
# was lost). check_perms.py names what is missing and emails the fix once a day.
if ! "$PYTHON" -u check_perms.py --bot "Shopee Bottom Account" \
        --alert "$STATE_DIR/permalert_$STAMP" >> "$LOG" 2>&1; then
    log "macOS permission missing — alert sent, will retry next tick"
    exit 0
fi

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

# Do not push a capture whose metrics the bot itself flagged as wrong. The
# screenshot exists and looks like a real page, so a file-existence check waves
# it through — that is how wrong charts reached the decks on 2026-09-24,
# 2026-10-01 and again on 2026-10-08. The brand is left for a redo instead; its
# slide keeps last week's chart, which is wrong-but-old rather than wrong-and-new.
# Only this tick's lines (the daily log also holds earlier ticks), and minus the
# brands the retry pass then captured cleanly ("RETRY OK for X").
TICK_LOG=$(awk '/===== tick =====/{buf=""} {buf=buf $0 "\n"} END{printf "%s", buf}' "$LOG")
RETRIED_OK=$(echo "$TICK_LOG" | grep -oE "RETRY OK for [A-Z0-9.-]+" | awk '{print $NF}' | sort -u)
BAD=$(echo "$TICK_LOG" | grep -oE "NOT AS REQUESTED for [A-Z0-9.-]+" | awk '{print $NF}' | sort -u \
      | grep -vxF -f <(echo "$RETRIED_OK") 2>/dev/null)
INSERTABLE=""
# Only brands captured TODAY. insert_to_slides.py picks the newest file per brand,
# so a brand that failed today would otherwise get an OLD chart pushed in as if it
# were new — on 2026-11-05 SOFT-M got 29/10's and CTW-M got 24/09's.
NOSHOT=""
for b in ${=BRANDS}; do
    echo "$BAD" | grep -qx "$b" && continue
    if [ -f "screenshots/SHO_${b}_1bulan_$STAMP.png" ] || [ -f "screenshots/${b}_1bulan_$STAMP.png" ]; then
        INSERTABLE="$INSERTABLE $b"
    else
        NOSHOT="$NOSHOT $b"
    fi
done
[ -n "$NOSHOT" ] && log "NOT inserting (no screenshot today, deck keeps last week's):$NOSHOT"
if [ -n "$BAD" ]; then
    log "⚠ NOT inserting (metrics flagged wrong): $(echo $BAD | tr '\n' ' ')"
fi

if [ -z "$INSERTABLE" ]; then
    log "no brand passed the metric check — skipping Slides entirely"
    INS_RC=1
else
"$PYTHON" -u insert_to_slides.py ${=INSERTABLE} >> "$LOG" 2>&1
INS_RC=$?
fi
log "slides step exit $INS_RC"

# Archive the captures for other systems to read. Runs AFTER the deck work and
# never gates it: a storage outage must not turn a good run into a failed one,
# so a non-zero exit here is logged and otherwise ignored.
"$PYTHON" -u gcs_upload.py >> "$LOG" 2>&1 \
    || log "WARNING: GCS archive upload failed — screenshots are still on disk"

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
