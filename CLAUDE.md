# Bottom Account Automation

Weekly Thursday automation: screenshot Shopee ads performance for underperforming brands and insert the images into Google Slides, one slide per brand.

**Since 2026-09-16 only "1 bulan terakhir" is captured and inserted** — the user dropped "3 bulan terakhir". The active date ranges live in `config.DATE_FILTERS` (currently `["1bulan"]`); every script (bot, insert, rescue, manual capture) loops over that list, and the 3-bulan coords/labels are kept so appending `"3bulan"` re-enables it end-to-end.

## Context

"Bottom Account" is a weekly meeting where underperforming brand ads are reviewed. The manual flow is highly repetitive — 51 shops on `ahacommerce.biteam`, only a subset flagged "bottom" each week. The user handles CAPTCHA/OTP at login; the bot handles the rest via PyAutoGUI on the default browser (macOS). Originally calibrated on a 2560x1664 Retina panel (1710x1112 logical, screencapture 2x); **since 2026-09-21 the user runs it on an external Mi Monitor, 1920x1080 at 1x** — the scale is detected at runtime (see **Display scale**) and every coord was recalibrated for that screen (see **Coordinates**).

## Files

- `shopee_ads_screenshot.py` — PyAutoGUI bot. Drives the browser, takes cropped screenshots, saves to `screenshots/`.
- `insert_to_slides.py` — Inserts screenshots into both the template deck and meeting deck. Duplicates template slide for template deck; replaces images in-place for meeting deck.
- `read_brands_from_sheet.py` — Fetches brand list from Google Sheet "Bottom" tab via service account. Skips red-text rows (belum sebulan) and HOL (Lazada-only).
- `send_email.py` — Gmail transport (`send_email`), plus `send_login_reminder` and the legacy `send_success_report`.
- `report_run.py` — Builds and sends the per-brand outcome report (added 2026-09-21). See **Run reporting**.
- `config.py` — URLs, Slides IDs, email recipients, timing constants, and `DATE_FILTERS` (which date ranges to capture/insert; `["1bulan"]` since 2026-09-16).
- `popups.py` — Registry of known blocking popups + template-match detection and dismissal (added 2026-09-21). See **Popups**. Run `python3 popups.py` to ask what it sees, `--capture` to grab a frame of a new one, `--dismiss` to close what it knows.
- `display.py` — Logical↔physical pixel conversion and `save_debug_shot()` (added 2026-09-21).
- `preflight.py` — Enforces the calibrated window/Dock geometry and reports session state by exit code (0 ready / 1 not logged in / 2 error). Run it before any unattended run; see **Scheduled weekly run**.
- `run_weekly.sh` / `com.aha.bottom-account.plist` / `bottom-account-run.app-wrapper.sh` — the Thursday schedule. See **Scheduled weekly run**. Measures the display scale at runtime; see **Display scale** below. Everything that reads pixels or crops goes through it.
- `brands.csv` — Maps brand `akun` → `shopee_username`. What the bot reads at runtime.
- `sync_brands_from_sheet.py` — Syncs `brands.csv` from the mapping source of truth (since 2026-08-06): sheet `1s4MAeV0TMoIA8i0t5xHlxsj01j5uDlNmOliIt7biknY` tab **"Monitored Stores"** (A = akun, B = username Shopee, C = kode partner; rows 1–2 are title/header, values need stripping). Appends new brands; username conflicts are reported but NOT overwritten, so a csv value verified against a live capture cannot be clobbered. **Source changed 2026-09-21** to sheet **"FBI: Daftar Akun"** `1nYuAvZFQ9XxxX6EDbL0XiK78op7JjuyuKY6auGhdF0I`, tab **"Akun"** — one row per account per marketplace, so rows are filtered to `MP == "SHO"` (column A); column D is the username, and for LAZ/TOK/TIK rows it is a display name instead. `--dry-run` to preview. The old note claiming the sheet had stale usernames "e.g. TH.WONE-M" was **backwards**: verified live 2026-09-21 that the real username is `woonae_official_shop` (both sheets agreed, csv's `woonae` was the stale one) — csv has been corrected.
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
9. For each filter in `config.DATE_FILTERS` (only `1 bulan terakhir` since 2026-09-16): open date filter, pick option, screencapture, crop to the Performa region (offset-adjusted), pad to `SCREENSHOT_ASPECT`, save.
   - **The date control is a calendar, not a plain dropdown** (confirmed 2026-09-21). Clicking `DATE_FILTER_DROPDOWN` opens a two-month date-range picker with a **preset list down its left side**: Hari Ini (y=510), Kemarin (542), 1 Minggu Terakhir (575), **1 Bulan Terakhir (606)**, **3 bulan terakhir (638)**. `FILTER_1BULAN`/`FILTER_3BULAN` point at those presets. Clicking a preset applies it immediately — there is no Apply/Konfirmasi button — and the page does not reflow, so the offset stays valid.
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

## Display scale

**Changed 2026-09-21** when the user moved from the MacBook's Retina panel to an external **Mi Monitor (1920x1080, 1x)**.

pyautogui clicks in *logical* points; `screencapture` writes *physical* pixels. The bot used to hardcode the ratio as `* 2` (Retina) in every pixel read and crop. On a 1x display that broke twice over:

- **Crash:** pixel reads ran off the frame — the ROAS card at logical (1446, 612) became (2892, 1224) in a 1920x1080 image → `IndexError`.
- **Silent corruption (worse):** the crop box landed entirely outside the capture. PIL pads an out-of-bounds crop with black instead of raising, so the bot would have reported success and pushed black images into both meeting decks.

`display.py` now measures the real ratio once per run from an actual screencapture and exposes:

- `scale()` — physical px per logical point, measured lazily and cached; prints e.g. `[display] 1920x1080 logical, 1920x1080 captured -> scale 1x` at the start of a run.
- `px(v)` / `to_logical(v)` — the two conversions.
- `sample(img, lx, ly)` — RGB at a logical coord, or **`None` if outside the capture**. The detectors skip `None` samples, so stale coords degrade the detection instead of killing the run with an `IndexError`.
- `crop_logical(img, l, t, r, b)` — returns `(image, clamped)`. `clamped=True` means the box reached outside the frame; `take_screenshot` prints a loud `⚠ CROP OUT OF BOUNDS` and says not to insert that image. **This is the guard against the silent-black-image failure — don't drop it.**

Crop output stays in physical pixels, so a Retina run still produces a full-resolution 2x image; only the *logical* geometry is scale-independent.

Threshold constants that were written in screen px (`detect_y_offset`'s scan range, run lengths, row pitch) are now **logical** and live in `shopee_ads_screenshot.py` as `CARD_SCAN_TOP_Y` / `CARD_SCAN_BOTTOM_Y` / `CARD_RUN_MIN` / `CARD_RUN_LO`,`CARD_RUN_HI` / `CARD_PITCH_LO`,`CARD_PITCH_HI`. `_rescue_capture.py` imports them (plus `bot._white_runs`) so both detectors re-tune from one place; its own `ALIGN_TOLERANCE` / `VERIFY_RUN_LO`,`VERIFY_RUN_HI` are logical too.

**`display.py` fixes the scale, NOT the layout.** All coords below are still calibrated for 1710x1112 and must be re-recorded for the 1920x1080 monitor.

## Coordinates

All click targets are hardcoded at the top of `shopee_ads_screenshot.py` and were calibrated for a **1710x1112** logical viewport (the old MacBook screen). If the browser window size, zoom, display, or Shopee's layout changes, run the relevant `--calibrate*` flag to re-record them. Every coord in the file is logical; conversion to capture pixels goes through `display.py`.

**Recalibrated 2026-09-21** for the 1920x1080 Mi Monitor, measured from a live screencapture (pixel analysis of element borders, not hover — see the note under **Metric card positions**). Verified end-to-end on BR: search → Detail → Iklan page → tab → offset detect → metric toggle → date filter → crop.

| Coord | Old (1710x1112) | New (1920x1080) |
|---|---|---|
| `SEARCH_BOX` | (488, 328) | **(735, 284)** |
| `FIRST_DETAIL_LINK` | (1216, 535) | **(1331, 495)** |
| `NAMA_TOKO_DROPDOWN` | (386, 322) | **(470, 284)** |
| `USERNAME_TOKO_OPTION` | (394, 401) | **(455, 361)** |
| `SEMUA_IKLAN_PRODUK_TAB` | (280, 430) | **(277, 398)** |
| `DATE_FILTER_DROPDOWN` | (1110, 446) | **(1349, 466)** |
| `FILTER_1BULAN` | (662, 574) | **(850, 606)** |
| `FILTER_3BULAN` | (662, 606) | **(850, 638)** |
| `CROP_TOP_LEFT` | (209, 413) | **(209, 440)** |
| `CROP_BOTTOM_RIGHT` | (1616, 963) | **(1820, 975)** |
| `EXPECTED_CARD_TOP_Y` | 471 | **500** |

The old coords were not merely stale, they were dead: the blue-pixel probe at the old `FIRST_DETAIL_LINK` scored **0** against a threshold of 10.

### Environment the calibration assumes

These coords are only valid with the screen set up the way it was calibrated. Reproduce this before a run, or recalibrate:

- **Display:** Mi Monitor, 1920x1080 at 1x, as the main display.
- **Chrome window bounds `{0, 30, 1920, 1080}`** — full width. (A 1710-wide window was tried to reproduce the old proportions exactly, but it leaves other windows visibly peeking out on the right; the aspect-ratio problem that motivated it is solved by padding instead — see `SCREENSHOT_ASPECT`.)
- **Dock set to auto-hide** (changed 2026-09-21; it was permanently visible, costing 90px). The bot still parks the pointer away from the bottom edge before capturing.
- **Chrome bookmarks bar hidden** (Cmd+Shift+B) — it costs ~28px of viewport.

Together those give a ~904px viewport for a 535px crop, restoring roughly the vertical slack the old 1710x1112 screen had. That slack is what absorbs the per-brand variation in where the Performa section lands.

Calibration flags (`--calibrate`, `--calibrate-cards`, `--calibrate-crop`) use **osascript dialogs** with a 5s hover delay (no `input()` since the script runs without a TTY). For card and crop calibration, the helpers `_calibrate_helper.py` / `_calibrate_crop_helper.py` first navigate to a brand's Iklan Shopee page and scroll, so the page is set up before dialogs prompt for hovers.

## Metric card positions

8 cards in 2 rows, 4 per row. **Recalibrated 2026-09-21** on the 1920x1080 monitor. Current layout (top row first):

- Row 1 (y=**540**): Tayangan, Jumlah Klik, Persentase Klik, Pesanan
- Row 2 (y=**640**): Produk Terjual, Penjualan dari Iklan, Pengeluaran, ROAS
- Columns are an even grid at x = **414 / 815 / 1215 / 1616** (~401 logical px apart).

Measured from the card **borders** in a live screencapture rather than by hover: horizontal borders at y=499/582 (row 1) and y=599/682 (row 2); vertical borders at x=222/606, 623/1007, 1024/1407, 1424/1808. Card interior is 83px tall, rows are 100px apart. Deriving centres from borders avoids the old failure where hover calibration landed 2 of 8 points in the gaps between cards.

**The live UI labels differ from the dict keys.** This Shopee build shows "Iklan Dilihat", "Penjualan" and "Biaya Iklan" — the 2026-06 rename to Tayangan/Penjualan dari Iklan/Pengeluaran appears to have been **reverted**. Only positions matter; the keys are kept so `DESIRED_SELECTED` still lines up. Don't "fix" the keys without also fixing `DESIRED_SELECTED`.

Detection: scans a strip above the card center (`dy -95..-4`, `dx ±80`) for a colored top border (saturation > 0.25, max channel > 100); `colored_count >= 5` ⇒ selected. Verified 2026-09-21: the border sits at **dy = -41** from centre, reading `rgb(58,115,219)` blue for a selected chart-1 metric and `rgb(239,111,71)` orange for chart-2 (ROAS). A live run correctly read Iklan Dilihat + ROAS as ON and the other six as off, then toggled to exactly Pengeluaran + ROAS.

## Auto-detect y-offset

`detect_y_offset()` is called after `scroll_to_performa()` and the Semua Iklan Produk tab click in each brand's flow. It screencaptures, then `_white_runs()` scans a vertical line in the clean white right portion of the Tayangan card (logical x tried at 500/480/520/460) between `CARD_SCAN_TOP_Y` and `CARD_SCAN_BOTTOM_Y` (logical 200–900), collecting every white run (`R,G,B > 248`). Runs are returned in **logical px** regardless of display scale. It then looks for the **structural pattern of two long white runs** — each `CARD_RUN_LO..CARD_RUN_HI` (65–100 logical) tall, tops `CARD_PITCH_LO..CARD_PITCH_HI` (90–110 logical) apart — that's row 1 + row 2 card interiors at the row pitch. The top of the first matching run = actual row 1 top. Offset = `actual_top - EXPECTED_CARD_TOP_Y` (= 471), refused if `|offset| > 120`. The offset is threaded into `is_card_selected` (via pre-adjusted card positions), `select_date_filter`, and `take_screenshot` so all clicks/screenshots track the actual layout per brand.

(Before 2026-09-21 these thresholds were written in Retina screen px — scan 400–1800, run ≥120, pitch 180–220, run 130–200. They are the same numbers halved; if you find an old note quoting the screen-px figures, it predates the scale refactor.)

**RESOLVED 2026-09-21** (was a KNOWN ISSUE since 2026-06-11, where detection always fell back to offset=0). With `EXPECTED_CARD_TOP_Y` re-anchored to **500** and the thresholds converted to logical px, detection works again: a live run on BR logged *"Card top detected at logical y=500 (offset +0, x=500)"*, and `+3` on a run where the page had settled slightly differently. The fallback message now means something is genuinely wrong rather than being the normal case — so if you see *"Could not detect card position"*, investigate instead of ignoring it.

Why it's needed: brands like ALUN-M and TH.KSB-M have less promo/banner content above the Performa section, so the fixed `pyautogui.scroll(-7, -8, -3)` lands the cards ~80–100 logical px higher than for brands with full banners. Without the offset, the bot would click row-1 coords and hit row-2 cards (or vice versa) and the crop would clip the cards while leaking "Semua Daftar Iklan" at the bottom.

Why two-run pattern (added 2026-05-11): the old single-run scan false-matched plain white space above the cards (e.g., the gap between promo banners and the tabs row on the Iklan Toko view), returning offsets like -217 that cascaded into the date-option click landing on the "Iklan Toko" tab and silently switching tabs mid-run. Requiring the two-row pattern eliminates that false match — empty white space produces only one run.

## Popups

**The old detector only ever saw half the problem.** `is_popup_present()` samples three points for a *dimmed dark backdrop* (`r,g,b < 80`). Plenty of Shopee popups have a LIGHT backdrop and are invisible to it — measured 2026-09-21 on the "Rekomendasi Iklan" promo card, where all three points read pure white `(255,255,255)` while the card was plainly on screen. CLAUDE.md already listed two others that slipped through the same way ("Bonus Eksklusif", "Aktifkan Optimasi pada Periode Promo"); the workaround was a 15s manual pause in `click_iklan_shopee` plus blind Escapes in `_rescue_capture`. **Escape does not close these promo cards** — they have an X that must be clicked.

`popups.py` adds a registry checked *before* the backdrop test. `close_popup()` now runs `popups.dismiss()` first, then falls back to the Escape path, then — if still stuck — **saves a frame** and tells you to register it.

### Why template matching, not sample points

The first attempt used fixed sample points and failed in both directions, which is worth remembering before anyone "simplifies" it back:

- The card **drifts ~15px** between frames, so a known-present popup scored only 1 of 3 signature points.
- Shopee's pages are **full of the same orange** (the Iklan page has ~14k orange pixels in that region), so a popup-free frame scored 2 of 3.

Matching a distinctive patch (the orange "Buka" button, `ref_images/popup_rekomendasi_iklan_buka.png`) inside a search window fixes both. Validated on 9 real frames: both popup-present frames score **0.0**, the nearest popup-free frame scores **36.1**, threshold sits at **18**. ~29ms per frame. Because the match returns *where* the card is, the close target is computed as an offset from it — so the X is clicked correctly even when the card has shifted (verified: (1828,208) in one frame, (1843,208) in another).

### Adding a new popup

One screenshot is enough — the bot now saves one automatically on an anomaly (`_dbg_*.png`), or run `python3 popups.py --capture` while it is up. Then follow the ADDING A NEW POPUP steps in `popups.py`. **Verify the close coordinate visually** by drawing a marker on it and looking: text strokes share the X's grey, and the first measurement during this work landed on the word "Iklan" rather than the X.

## Evidence on failure

The bot runs unattended; by the time anyone looks, the screen is gone. `display.save_debug_shot(tag)` writes `screenshots/_dbg_<tag>_<timestamp>.png`, and is now called when:

- **`detect_y_offset` fails** (`_dbg_offset_detect_failed_*`). Since the recalibration this is no longer the normal case, so it means something real — a popup over the cards, a layout shift, a half-loaded page.
- **the metric cards do not end up as requested** (`_dbg_metrics_<AKUN>_*`). `process_brand` re-checks all 8 cards after toggling; a click that missed otherwise yields a plausible-looking screenshot of the *wrong metrics* that would go into both decks unnoticed.
- **an unrecognised popup blocks the run** (`_dbg_unknown_popup_*`).

Pre-existing: `_dbg_detail_fail_*` (search found no shop), `_dbg_rescue_fail_*` / `_dbg_rescue_shift_*`.

## Scheduled weekly run (added 2026-09-21)

Fires **Thursdays, every 15 min from 07:30 to 09:00**, and stops as soon as a run succeeds.

| Piece | What it does |
|---|---|
| `com.aha.bottom-account.plist` | LaunchAgent, 7 Thursday ticks. Points at the .app, never at `/bin/zsh`. |
| `~/Applications/Bottom Account Run.app` | Permission + PATH wrapper. Source kept here as `bottom-account-run.app-wrapper.sh`. |
| `run_weekly.sh` | Orchestrates one tick: markers, lock, preflight, run, report. |
| `preflight.py` | Enforces the calibrated geometry, then reports whether the session is alive. |
| `com.aha.bottom-probe.plist` | On-demand permission check: `launchctl start com.aha.bottom-probe`, read `logs/probe.log`. |

### Why it cannot simply run unattended

- **Login needs CAPTCHA/OTP**, which only a human can do. The Shopee session usually survives between Thursdays, so most weeks no login is needed — but not all.
- **It takes the mouse and keyboard for ~an hour.** The Mac must be left alone.
- The Mac itself is fine: `pmset` shows `sleep 0` / `displaysleep 0`, so it is awake at 07:30.

So each tick is idempotent and decides for itself:

1. `logs/state/done_<date>` exists → exit at once (this is why the 15-min retries are cheap).
2. `logs/state/run.lock` held (atomic `mkdir`) → another tick is mid-run, exit.
3. `preflight.py` → **2** Chrome unavailable: retry next tick. **1** session expired: send the login reminder *once* (`logs/state/reminded_<date>`) and wait — the user only has to log in, the next tick picks it up. **0** ready: full run, then mark done.
4. Screenshots failing does **not** proceed to Slides; it marks done so the retry loop stops, and the run is redone by hand with `run_bottom.command`.

### The permission trap — do NOT point the agent at /bin/zsh

macOS attributes Screen Recording / Accessibility to the **responsible process**. Verified 2026-09-21: with launchd invoking `/bin/zsh` directly, preflight drove Chrome through AppleScript fine but `screencapture` died with **"could not create image from display"** — and the whole bot rests on screencapture. Granting the permission to `/bin/zsh` would also hand it to every shell script on the machine.

The fix is the same .app wrapper `com.aha.priceguard.tick` already uses (whose own comments record this costing 6 days of misdiagnosis in August). It also forces `PATH=/opt/homebrew/bin:...`, because launchd's minimal PATH otherwise resolves `python3` to `/usr/bin/python3`, which has no pyautogui or PIL.

**No extra permission grant is needed, and the bundle will not appear in the Screen Recording list — that is expected.** Every capture in the bot is driven from python, and `python3.14` already holds the grant; through the .app wrapper that grant applies. Verified 2026-09-21: `capture (py): OK (1920, 1080)` and a full `preflight exit: 0` under launchd. A bare `screencapture` straight from the wrapper's shell still fails — harmless, since nothing in the bot calls it that way. Don't chase it.

### Frontmost ≠ logged in

`preflight` activates Chrome and then **confirms Chrome actually came forward** (retrying 3×), and re-confirms right before the capture. Without that check the capture shows whatever window was really on top, the shop table reads as missing, and the run reports "session expired" — emailing the user to log in when the session is perfectly fine. Observed 2026-09-21: preflight flipped from exit 0 to exit 1 minutes apart purely because the editor held the front. A focus problem now returns **2** (environment, retry next tick), never **1** (login).

### Paths were all dead

All four shell scripts still pointed at `/Users/claudia/bottom-account-automation` and a Python 3.13 framework build, neither of which exists here. Corrected to `/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot` and `/opt/homebrew/bin/python3` (3.14.4).

### What is verified, and what is not

Verified on real runs 2026-09-21 (screenshots only — Slides insertion was deliberately not exercised):

- Preflight under launchd via the .app: exit 0, session alive.
- 6 brands captured cleanly (BR, MON-M, HYDR-M, SOFT-M, GOJI-M, TH.STAR-M), every one with `detect_y_offset` reporting +0/+3 and the metric check confirming only Pengeluaran + ROAS.
- **TH.STAR-M proves the `.co.th` path works** — its figures render in Baht (฿).
- The skip guard works: LEAG-M, TH.KSB-M and KENL-M returned "Shop (0) — Toko tidak ditemukan" and were skipped rather than screenshotting whichever shop was previously selected.

**Full chain rehearsed end-to-end 2026-09-21** on HYDR-M, SOFT-M, GOJI-M — preflight → mapping sync → screenshots → `insert_to_slides.py` → report email, all exit 0, report `3/3 done`. Verified afterwards against a before/after snapshot of all three decks:

- Slide counts unchanged in every deck, as expected (template deletes the brand's slide then duplicates the template; meeting decks replace the image in place).
- New image objects present and **not distorted**. Template-deck images land at exactly **2.557**, matching `SCREENSHOT_ASPECT` (1407/550 = 2.558).
- Meeting-deck boxes are **not uniform** — measured 2.557, 2.581, 2.628, 2.648 across brands, because each new image inherits `old_size`. The worst case (SOFT-M at 2.628 vs our 2.557, a 2.8% squeeze) was rendered via `pages().getThumbnail()` and shows no visible distortion. Padding was still the right call: without it the images would be 3.01 and ~18% off.
- `meeting1` ("Copy of FBI Bottom Account (17 April 2026)") holds **no slides at all** for SOFT-M or GOJI-M, so those are skipped with "No … ROAS slide for …". That is expected for an older deck, not a failure.
- Stale `3bulan` image objects still sit on the 3-bulan slides, untouched, exactly as intended since 2026-09-16.

Still unproven: any brand needing `_rescue_capture`, and the generic modal handler closing a *live* popup (it is validated only against a saved frame).

### Turning it off

```
launchctl unload ~/Library/LaunchAgents/com.aha.bottom-account.plist
```

## Brand list vs brand mapping — do not confuse them

| | Source | Notes |
|---|---|---|
| **Which brands to run this week** | "Bottom" tab, sheet `1POC6XDI…`, column C | Refreshed every Thursday. This has ALWAYS been the source — the original `run_weekly.sh` called the bot with no args, which makes `main()` fetch from the sheet. |
| **akun → Shopee username** | `brands.csv`, synced from "Monitored Stores" | The Bottom tab carries **no username column** (its columns are Akun, GMV L30D, % GMV, Umur, MOSO, Before AHA), and Pilih Toko searches by username — so the mapping has to come from somewhere. |

`brands.csv` is **never** the source of the weekly list. Passing brands as CLI args is the only path that bypasses the sheet, and it exists for manual reruns.

`run_weekly.sh` now syncs the mapping **before** reading the week's list, so a renamed or newly-added shop is picked up automatically. The sync only adds and reports; it never overwrites a username conflict, so a verified csv value cannot be clobbered by a stale sheet entry. A sync failure logs a warning and the run continues on the existing csv.

### Mapping sources compared (2026-09-21)

Same spreadsheet `1s4MAeV0TMoIA8i0t5xHlxsj01j5uDlNmOliIt7biknY` ("File Harga All Brand") holds two candidate tabs. **"Monitored Stores" is the current one** — do not switch to the other:

- **Monitored Stores** (A=akun, B=username, C=kode partner, data from row 3): 67 entries.
- **Daftar Akun** (A=Kode Brand, B=Nama Toko, C=Kode Partner, data from row 2): 55 entries, and **older** — missing GOJI-M, LEAG-M, CALC-M, COVM-M, DGLV-M and others that are live and working.

## Run reporting

**Until 2026-09-21 a completed run sent nothing.** `run_weekly.sh` only ever sent the *login reminder*; there was no result email, so a Thursday run — whether it succeeded or half-failed — finished in silence.

The legacy `send_email.send_success_report()` was also misleading: it prints *"Screenshots have been inserted into Google Slides"* unconditionally, without checking the Slides step, so a run whose insertion failed would still report success. It is left in place for any old caller, but the scheduled path no longer uses it.

`report_run.py` replaces it and reads status back from **evidence, not assumption**:

- **screenshot** — the file `screenshots/{AKUN}_{filter}_{today}.png` actually exists;
- **inserted** — the brand does not appear in `insert_to_slides.py`'s failure output (`✗ AKUN FAILED`, or the `⚠ FAILED brands` block) *and* that step exited 0.

It also parses the bot's `NOT FOUND (skipped …)` block, so a brand whose shop is not on the account is reported as such rather than as a vague failure. Output is a per-brand table plus an explicit **NEEDS A MANUAL REDO** list, which is what CLAUDE.md has always required of the report.

Wired into **both** exit paths of `run_weekly.sh` — including the screenshots-failed branch, so a broken run still reports itself. A failure to send is logged as a warning and never masks the run's own exit code.

`--dry-run` prints the email instead of sending it; `--subject-prefix` tags non-production runs.

## Gotchas

- **Pilih Toko search is a SUBSTRING match.** Searching `woonae` returns the shop whose username is `woonae_official_shop`. So a slightly-wrong-but-prefix username still works, which is why a stale mapping can hide for months. The flip side is diagnostic: a `Shop (0) — Toko tidak ditemukan` result is therefore strong evidence the shop genuinely is not on this account, not merely that the username is a bit off (seen 2026-09-21 for LEAG-M, TH.KSB-M, KENL-M).

- `pyautogui.FAILSAFE = True` — slam the mouse to a corner to abort.
- **Chrome must be frontmost before any pyautogui click or screencapture.** Anything driving the UI from a script has to `osascript -e 'tell application "Google Chrome" to activate'` and sleep ~2s first, or the click lands on — and the capture shows — whatever window is in front (the terminal, typically). This bit the calibration work directly.
- **The saved PNG is padded, not cropped, to `SCREENSHOT_ASPECT`.** Don't "simplify" `take_screenshot` by dropping `pad_to_aspect`: the meeting decks force each new image into the old image's box, so an unpadded 3.01:1 capture gets stretched on every brand's slide. Padding is white and the crop edges are white, so it is invisible.
- **Never hardcode a pixel ratio again.** Anything reading a screencapture or cropping one goes through `display.py`; a bare `* 2` is a bug on the current 1x monitor. See **Display scale**.
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
