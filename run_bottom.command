#!/bin/zsh
# Bottom Account — one-click full run.
# Double-click this file to: fetch this week's bottom brands from the Google
# Sheet, screenshot Shopee ads for each, then insert images into the slide decks.
#
# IMPORTANT: log in to Shopee and be on the "Pilih Toko" page BEFORE the 10s
# countdown ends — the bot drives whatever browser tab is in front.

PROJECT_DIR="/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot"
PY="/opt/homebrew/bin/python3"

cd "$PROJECT_DIR" || { echo "Project dir not found: $PROJECT_DIR"; read "?Press Enter to close..."; exit 1; }

echo "=================================================="
echo "  Bottom Account — Full Run"
echo "=================================================="
echo "Fetching this week's brands from the Google Sheet..."

# Fetch brands ONCE (filtered to brands.csv) so the screenshot and slides steps
# operate on the exact same list, even if the sheet changes mid-run.
BRANDS=$("$PY" - <<'PYEOF'
import csv
from read_brands_from_sheet import fetch_bottom_brands

valid = set()
with open("brands.csv") as f:
    for row in csv.DictReader(f):
        valid.add(row["akun"].strip())

brands = [b for b in fetch_bottom_brands() if b in valid]
print(" ".join(brands))
PYEOF
)

if [ -z "$BRANDS" ]; then
    echo "⚠ No brands found in the sheet (or none matched brands.csv). Nothing to do."
    read "?Press Enter to close..."
    exit 1
fi

echo "Brands: $BRANDS"
echo ""

# 1) Screenshots
echo ">>> Step 1/2: Screenshots"
"$PY" shopee_ads_screenshot.py ${=BRANDS}
SHOT_RC=$?

if [ $SHOT_RC -ne 0 ]; then
    echo ""
    echo "⚠ Screenshot step exited with code $SHOT_RC — skipping Slides insertion."
    echo "  Fix the issue and re-run, or insert manually:"
    echo "    $PY insert_to_slides.py $BRANDS"
    read "?Press Enter to close..."
    exit $SHOT_RC
fi

# 2) Insert into slide decks
echo ""
echo ">>> Step 2/2: Insert into Slides"
"$PY" insert_to_slides.py ${=BRANDS}
INS_RC=$?

echo ""
echo "=================================================="
if [ $INS_RC -eq 0 ]; then
    echo "  ✅ Full run complete."
else
    echo "  ⚠ Slides insertion exited with code $INS_RC — check output above."
fi
echo "=================================================="
read "?Press Enter to close..."
