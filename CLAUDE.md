# Bottom Account Automation

Weekly Thursday automation: screenshot Shopee ads performance for underperforming brands and insert the images into Google Slides, one slide per brand.

**Since 2026-09-16 only "1 bulan terakhir" is captured and inserted** — the user dropped "3 bulan terakhir". The active date ranges live in `config.DATE_FILTERS` (currently `["1bulan"]`); every script (bot, insert, rescue, manual capture) loops over that list, and the 3-bulan coords/labels are kept so appending `"3bulan"` re-enables it end-to-end.

## Context

"Bottom Account" is a weekly meeting where underperforming brand ads are reviewed. The manual flow is highly repetitive — 51 shops on `ahacommerce.biteam`, only a subset flagged "bottom" each week. The user handles CAPTCHA/OTP at login; the bot handles the rest via PyAutoGUI on the default browser (macOS, 2560x1664 Retina → pyautogui uses 1710x1112 logical coords, screencapture returns 2x).

## Files

- `shopee_ads_screenshot.py` — PyAutoGUI bot. Drives the browser, takes cropped screenshots, saves to `screenshots/`.
- `insert_to_slides.py` — Inserts screenshots into both the template deck and meeting deck. Duplicates template slide for template deck; replaces images in-place for meeting deck.
- `read_brands_from_sheet.py` — Fetches brand list from Google Sheet "Bottom" tab via service account. Skips red-text rows (belum sebulan) and HOL (Lazada-only).
- `send_email.py` — Sends email notifications via Gmail API (login reminders and success reports).
- `config.py` — URLs, Slides IDs, email recipients, timing constants, and `DATE_FILTERS` (which date ranges to capture/insert; `["1bulan"]` since 2026-09-16).
- `brands.csv` — Maps brand `akun` → `shopee_username`. What the bot reads at runtime.
- `sync_brands_from_sheet.py` — Syncs `brands.csv` from the mapping source of truth (since 2026-08-06): sheet `1s4MAeV0TMoIA8i0t5xHlxsj01j5uDlNmOliIt7biknY` tab **"Monitored Stores"** (A = akun, B = username Shopee, C = kode partner; rows 1–2 are title/header, values need stripping). Appends new brands; username conflicts are reported but NOT overwritten (verified csv values win — the sheet has had stale usernames, e.g. TH.WONE-M). `--dry-run` to preview. The old master-sheet BRAND tab was deleted 2026-08-06.
- `capture_ref_images.py` / `ref_images/` — Reference images for visual debugging / calibration aids.
- `mouse_tracker.py` — Helper to print live mouse position while calibrating.
- `_calibrate_helper.py` — Navigates to a brand's Iklan Shopee page, scrolls to Performa, then runs `calibrate_cards()` (used when the page must be set up before card calibration).
- `_calibrate_crop_helper.py` — Same as above but runs `calibrate_crop()` to re-record the screenshot crop region.
- `_calibrate_date.py` — Standalone date-filter calibration (assumes Iklan Shopee page already in view).
- `_calibrate_date_full.py` — Navigates to a brand's Iklan page + scrolls, THEN runs the date-filter calibration dialogs (use when starting from Pilih Toko). Records `DATE_FILTER_DROPDOWN`, `FILTER_1BULAN`, `FILTER_3BULAN`.
- `_calibrate_nama_toko.py` / `_calibrate_pilih_toko.py` — Live hover calibration for the Pilih Toko page coords (`NAMA_TOKO_DROPDOWN`, `USERNAME_TOKO_OPTION`, `SEARCH_BOX`, `FIRST_DETAIL_LINK`).
- `_setup_and_capture.py` — Navigates to a brand's Iklan page, scrolls, takes ONE full screencapture (`/tmp/cards_full.png`) for measuring card centers from the image (more accurate than hover). `_setup_and_track.py` — same nav, then live mouse-position tracker.
- `_manual_capture.py` — Manual screenshot fallback: dialogs prompt the user to set up the page (correct metrics + filter), bot just screencaptures with the calibrated crop. Use when auto-detect can't recover. NOTE: the browser must be the visible window when OK is clicked, or it captures whatever is in front (e.g. the terminal).
- `_rescue_capture.py` — Adaptive-scroll fallback (added 2026-07-23): navigates from Pilih Toko like the normal bot but replaces the fixed `scroll_to_performa` with small scroll steps that re-scan for the two-row card pattern until the cards sit in the crop window (accepts offset −80..+100), plus extra page-load wait. Use for brands whose Iklan page defeats the fixed scroll (e.g. KENL-M: extra Promosi/Misi Penjual sections + slow load push Performa far below the fixed landing point). A large positive offset can pull the macOS Dock into the crop bottom — trim the saved PNGs if needed.
- `credentials.json` / `token.pickle` — Google OAuth for Slides/Drive (gitignored).
- `token_gmail.pickle` — Google OAuth for Gmail send (gitignored).
- `service_account.json` — Service account key for Sheets read (gitignored).

## Usage

```
python3 shopee_ads_screenshot.py                   # auto-fetch brands from Google Sheet
python3 shopee_ads_screenshot.py BRAND1 BRAND2 ... # manual override
python3 shopee_ads_screenshot.py --calibrate       # re-record click coords
python3 insert_to_slides.py BRAND1 BRAND2 ...      # insert latest screenshots to both slide decks
```

Brand args are uppercased and must exist in `brands.csv`. Screenshots land in `screenshots/{AKUN}_{filter}_{YYYYMMDD}.png` where `filter` comes from `config.DATE_FILTERS` (now only `1bulan`; older `3bulan` files from before 2026-09-16 remain in the folder and are ignored by the insert step).

## Flow (per brand)

User must navigate to Pilih Toko page manually before starting the bot. The bot does NOT navigate there at the start — it assumes you're already on Pilih Toko.

1. Switch search filter to "Username Toko", type username, Enter.
2. Click first "Detail" link.
3. Navigate to Iklan Shopee via Cmd+L + URL:
   - Indonesian brands: `https://seller.shopee.co.id/portal/marketing/pas/index`
   - Thai brands (`TH.*`): `https://seller.shopee.co.th/portal/marketing/pas/index`
4. Popup handling: checks if dimmed overlay present → tries Escape (twice if needed) → only shows macOS dialog if popup persists. No notification if no popup.
5. Scroll down to "Performa Seluruh Iklan".
6. **Force "Semua Iklan Produk" tab**: click `SEMUA_IKLAN_PRODUK_TAB`. Shopee's tab choice is sticky across navigations within a session, so even though `/portal/marketing/pas/index` is the right URL, the page may open on whatever tab was last used (e.g. Iklan Toko). The explicit click is a no-op if already correct.
7. **Auto-detect y-offset**: scans for the top of row 1 cards (looks for the structural pattern of two long white runs — row 1 and row 2 interiors — separated by a short non-white gap, at the Tayangan column) and computes offset from calibrated `EXPECTED_CARD_TOP_Y`. The offset is then added to all card click positions, date filter clicks, and the screenshot crop region — handles brands where the page has less content above (e.g. ALUN-M, TH.KSB-M) so a fixed scroll lands the Performa section higher than calibrated. If the pattern isn't found (rare), falls back to offset=0.
8. Smart metric card detection: scans all 8 metric cards for colored top border (selected state). Deselects everything except **Pengeluaran + ROAS** (formerly "Biaya Iklan"). Only clicks cards that need toggling.
9. For each filter in `config.DATE_FILTERS` (only `1 bulan terakhir` since 2026-09-16): open date filter, pick option, screencapture, crop to the Performa region (offset-adjusted), save.
10. Go back to Pilih Toko via Cmd+L + `https://seller.shopee.co.id/portal/shop` (always `.co.id`, even for Thai brands).

## Domain handling

- Most brands → `seller.shopee.co.id`
- Brands starting with `TH.` → `seller.shopee.co.th` (for Iklan Shopee page only)
- Pilih Toko page is always `seller.shopee.co.id/portal/shop` (main account page)

## Google Sheet integration

- **Sheet:** `1POC6XDI1WEcSUEQG4rXgW5I2SkQwicduVJ9OY1wOW_4` tab **"Bottom"**
- Auto-updates every Thursday. Brand codes in column C ("Akun"), starting row 4.
- **Exclusions:** red-text rows (belum sebulan), HOL (Lazada-only).
- **Auth:** service account `bottom-ads-bot-shopee@fbi-dev-484410.iam.gserviceaccount.com`.

## Two presentations

### 1. Template deck (`SLIDES_ID`)

`1Ott0JcNme2979Obe4VpJNQey7Pyr6mP5YNGeK2XiFC4`

Uses a template slide (slide 1) that is duplicated once per brand per date filter — i.e. ONE slide per brand since 2026-09-16. Template contains:
- **Title placeholder** (top-left): brand name with hyperlink
- **Subtitle text box** (center-top): "SHO ROAS 1 Bulan Terakhir" (labels per filter in `FILTER_LABELS`; the 3-bulan label is kept for re-enabling), Nunito 22pt bold
- **Logo image** (top-right): AHA Commerce logo
- **Background image**: includes blue bar at bottom

Template IDs are hardcoded in `insert_to_slides.py`. If the template slide is recreated, update `TEMPLATE_SLIDE_ID`, `TEMPLATE_TITLE_ID`, `TEMPLATE_SUBTITLE_ID`, `TEMPLATE_LOGO_ID`, `TEMPLATE_RECT_ID`.

Existing slides for a brand are deleted before insertion (matched by title text = brand code) — so any leftover 3-bulan slides from before 2026-09-16 disappear the first time a brand is re-inserted. Images uploaded to Drive with `anyone/reader` permission. Always picks the latest screenshot file per filter (sorted by date suffix).

### 2. Meeting decks (`MEETING_SLIDES_IDS`)

Two meeting decks share the same structure, and the bot updates both:

- `12BCe2jvkoG1z01il6bBQRHkW3Z2aOSMUAIKG8JzqFuM` — original "FBI Bottom Account"
- `1f2QVMCagabXk6RidXLIYhpI6uBCVBougOKs7RPEotCE` — newer "FBI Bottom Account (13 Mei 2026)"

Each has hundreds of slides covering many topics per brand (GMV, harga, stok, profit, ads). Each brand has 4 ROAS slides: first pair = **Shopee**, second pair = **TikTok**. Bot finds the **first pair only** (Shopee) and, since 2026-09-16, replaces the image on the **1-bulan slide only** — the brand's 3-bulan Shopee slide is not touched, so whatever image it holds stays as-is (stale). Detection: finds slides with "ROAS" + "Bulan" in text, identifies brand name, takes the first match per filter.

`replace_meeting_screenshots()` iterates over `MEETING_SLIDES_IDS` from `config.py` — to add another deck, append its ID there. `MEETING_SLIDES_ID` (singular) is kept as a back-compat alias for `MEETING_SLIDES_IDS[0]`.

Brand names with dots (e.g., `TH.KSB-M`) are sanitized to underscores in Slides object IDs (dots are invalid).

## Email notifications

- **Recipients:** `tfbi@ahacommerce.net`, `claudia.ong@ahacommerce.net`
- **Login reminder:** sent before bot runs, includes brand list from Google Sheet
- **Success report:** sent after the FULL run finishes (screenshots + Slides insertion). Must list, per brand, whether the screenshot was captured and whether it was inserted into both decks. Surface any failures explicitly so the user knows which brands to redo manually.
- **Auth (changed 2026-06-26):** Gmail API via **service-account domain-wide delegation** — `send_email.py` loads `service_account.json` (same key used for Sheets), requests the `gmail.send` scope, and impersonates the sender with `.with_subject(EMAIL_SENDER)`. No more OAuth browser flow or `token_gmail.pickle` for email.
  - **DWD authorization (one-time, admin):** the service account's client ID `100244324578592545717` must be authorized in the Workspace Admin Console (Security → API Controls → Domain-wide Delegation) for scope `https://www.googleapis.com/auth/gmail.send`. Without it, sends fail with `unauthorized_client`.
  - The impersonated mailbox must be a **real Workspace account** in `ahacommerce.net` — DWD can't impersonate a non-existent user.
- **Sender:** `bot@ahacommerce.net`, display name **AHAbot™** (set via `EMAIL_SENDER` / `EMAIL_SENDER_NAME` in `config.py`). The From header UTF-8-encodes the ™ (`formataddr` + `Header`), so it transmits as `=?utf-8?b?...?=` and decodes back to AHAbot™ in mail clients.

## Coordinates

All click targets are hardcoded at the top of `shopee_ads_screenshot.py` and assume a 1710x1112 logical viewport. If the browser window size, zoom, or Shopee's layout changes, run the relevant `--calibrate*` flag to re-record them. Screenshot crop uses `CROP_TOP_LEFT` and `CROP_BOTTOM_RIGHT` multiplied by 2 for Retina.

Calibration flags (`--calibrate`, `--calibrate-cards`, `--calibrate-crop`) use **osascript dialogs** with a 5s hover delay (no `input()` since the script runs without a TTY). For card and crop calibration, the helpers `_calibrate_helper.py` / `_calibrate_crop_helper.py` first navigate to a brand's Iklan Shopee page and scroll, so the page is set up before dialogs prompt for hovers.

## Metric card positions

8 cards in 2 rows, 4 per row. **Shopee reordered the cards in 2026-04 and renamed two in 2026-06** (`Iklan Dilihat`→`Tayangan`, `Biaya Iklan`→`Pengeluaran`; order/positions unchanged). Current layout (top row first):

- Row 1 (y=512): Tayangan, Jumlah Klik, Persentase Klik, Pesanan
- Row 2 (y=612): Produk Terjual, Penjualan dari Iklan, Pengeluaran, ROAS
- Columns are an even grid at x = 390 / 742 / 1094 / 1446 (~352 logical px apart).

Detection: scans a strip above the card center (`dy -95..-4`, `dx ±80`) for a colored top border (saturation > 0.25, max channel > 100); `colored_count >= 5` ⇒ selected. The colored border sits ~41 logical px above center (`dy ≈ -42`).

Recalibrated 2026-06-11 after a layout shift (browser window moved ~30–40px up) + the card rename. **The card centers were measured directly from a live full screencapture (not hover)** — manual hover calibration kept landing 2 of 8 points in the gaps between cards, so `is_card_selected` scanned empty space and missed selected cards. If recalibrating, prefer measuring the grid from a screenshot (see `_setup_and_capture.py`) over blind hovers.

## Auto-detect y-offset

`detect_y_offset()` is called after `scroll_to_performa()` and the Semua Iklan Produk tab click in each brand's flow. It screencaptures, then scans a vertical line at the Tayangan column (logical x≈390, `METRIC_CARDS["Tayangan"][0]`) from screen y=400 to y=1800, collecting every white run (`R,G,B > 248`). It then looks for the **structural pattern of two consecutive long white runs** (each ≥100 screen px = ≥50 logical) separated by a short non-white gap (20–80 screen px) — that's row 1 + row 2 card interiors with the inter-row gap between them. The top of the first matching run = actual row 1 top. Offset = `actual_top - EXPECTED_CARD_TOP_Y` (= 517). The offset is threaded into `is_card_selected` (via pre-adjusted card positions), `select_date_filter`, and `take_screenshot` so all clicks/screenshots track the actual layout per brand.

**KNOWN ISSUE (2026-06-11):** after the card redesign, `detect_y_offset` no longer matches the two-run pattern and logs *"Could not detect card position, assuming offset=0"*. With the freshly-measured card grid, offset=0 is correct for brands with full banner content above Performa (verified on BR), but brands with **less** content above (ALUN-M, TH.KSB-M) that historically needed a nonzero offset may capture wrong. `EXPECTED_CARD_TOP_Y` (517) is also now slightly stale vs the measured row-1 card top (~471). Re-tune the detection / `EXPECTED_CARD_TOP_Y` for the new layout if those brands come out clipped.

Why it's needed: brands like ALUN-M and TH.KSB-M have less promo/banner content above the Performa section, so the fixed `pyautogui.scroll(-7, -8, -3)` lands the cards ~80–100 logical px higher than for brands with full banners. Without the offset, the bot would click row-1 coords and hit row-2 cards (or vice versa) and the crop would clip the cards while leaking "Semua Daftar Iklan" at the bottom.

Why two-run pattern (added 2026-05-11): the old single-run scan false-matched plain white space above the cards (e.g., the gap between promo banners and the tabs row on the Iklan Toko view), returning offsets like -217 that cascaded into the date-option click landing on the "Iklan Toko" tab and silently switching tabs mid-run. Requiring the two-row pattern eliminates that false match — empty white space produces only one run.

## Gotchas

- `pyautogui.FAILSAFE = True` — slam the mouse to a corner to abort.
- CAPTCHA/OTP at login is manual; start the script only after you're logged in and on Pilih Toko.
- Drive upload sleeps 3s before returning the URL so Slides' image fetcher doesn't 404 on a fresh file.
- All navigation uses Cmd+L + URL (sidebar clicks and "Ganti toko" dropdown were unreliable).
- Script runs non-interactively (no stdin) — use `osascript display dialog` for user prompts, not `input()`.
- Brand names with dots break Slides object IDs — sanitize to underscores.
- `click_iklan_shopee` waits `PAGE_LOAD_WAIT + 7` (= ~10s) after navigating — Shopee's Iklan page can be slow and a too-short wait causes the bot to scroll/click before the page is ready (e.g. landing on the "Iklan Live" tab).
- The bot's fixed-tick scroll (`scroll_to_performa`) lands at different positions across brands. The auto-detect y-offset compensates; don't assume row-1 cards are always at calibrated y.
- **Iklan Shopee tab is sticky across sessions.** Even with the right URL, Shopee opens whichever tab was last used (Iklan Toko, Iklan Banner, etc.). The bot always clicks `SEMUA_IKLAN_PRODUK_TAB` after scrolling to defend against this — do NOT remove that step.
- **When verifying calibrated coords, never use osascript Yes/No dialogs.** The dialog appears centered on screen and can physically cover the cursor at the hovered position, producing false-negative "No" answers even when the coord is correct. Use `pyautogui.moveTo` + `screencapture` + read the PNG to check where the cursor actually landed.
- **Wrong date filter clicks are usually `detect_y_offset` — but not always.** The usual cause is `detect_y_offset` returning a bad value (or the bot being on the wrong tab), which shifts every downstream click. Check the bot's stdout for the printed offset first. **EXCEPTION (2026-06-11):** after a layout shift, the date coords were genuinely stale — `DATE_FILTER_DROPDOWN (1103, 484)` landed ON the Persentase Klik card, so opening the dropdown toggled a metric and the date never changed. **Tell-tale of stale date coords:** the same extra metrics keep re-appearing in the final screenshot even after the bot logs deselecting them (the date-filter clicks fire AFTER metric-setting and re-toggle the cards underneath), and `detect_y_offset` printed offset=0. Fix with `_calibrate_date_full.py`; the new `DATE_FILTER_DROPDOWN` y must be ABOVE the card row (cards start ~y471).
