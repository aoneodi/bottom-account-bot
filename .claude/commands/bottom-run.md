---
description: Run the full weekly Bottom Account flow — screenshot Shopee ads, let the user verify, then insert into Slides and email a detailed report
argument-hint: "[BRAND1 BRAND2 ...] (optional — omit to auto-fetch this week's brands from the Sheet)"
---

# Bottom Account — full weekly run

Run the complete weekly Bottom Account pipeline for the user. The user has already
logged in to Shopee Seller Centre and is on the **Pilih Toko** page (that's the
precondition for the button that launched this). Drive it end-to-end, but **pause for
the user's visual verification before touching Google Slides** — that human check is
the whole point of running this through Claude instead of the raw cron job.

Python is at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`.
Work from `/Users/claudia/bottom-account-automation`.

## Brand list

- If the user passed brands as arguments (`$ARGUMENTS`), use exactly those (uppercased).
- Otherwise auto-fetch this week's list from the Google Sheet, filtered to `brands.csv`:
  ```
  python3 -c "import csv; from read_brands_from_sheet import fetch_bottom_brands; valid={r['akun'].strip() for r in csv.DictReader(open('brands.csv'))}; print(' '.join(b for b in fetch_bottom_brands() if b in valid))"
  ```
- Show the user the resolved brand list before starting.

## Step 1 — Screenshots

- Run `python3 shopee_ads_screenshot.py <BRANDS...>` **in the background** (it controls
  the screen via PyAutoGUI — remind the user once: "jangan sentuh mouse/keyboard, slam
  ke pojok untuk abort"). It has a 10s countdown, then ~1.5–2 min per brand.
- Stdout is buffered (not a TTY) so it won't stream live — wait for the background task
  to complete, then read the full output file.
- Since 2026-09-16 the bot captures **only `1bulan`** (one screenshot per brand — 3 bulan
  was dropped; see `config.DATE_FILTERS`). Don't expect or hunt for `3bulan` files.
- Parse the output for two things:
  - the **DONE!** list of saved screenshots (these succeeded), and
  - the **⚠ NOT FOUND** list (skipped — account not held). **STRO-M is a known
    not-held brand — that skip is expected, not a bug.** Don't try to recapture it.

## Step 2 — Verify (REQUIRED human gate)

- Read and display the saved screenshots inline (`Read` each PNG) so the user sees the
  grid. For each, confirm: the date-filter button reads **"1 Bulan Terakhir"** (that's the
  only range captured now), only **Pengeluaran/Biaya Iklan + ROAS** metric cards selected,
  and the crop framing is clean (date-filter button at top, no "Daftar Semua Iklan Produk"
  leaking at the bottom).
- Shop-switch check: compare each brand's metric numbers against every other brand of the
  day — near-identical values mean the bot silently stayed on another shop (re-run that
  brand). There is no 1b-vs-3b self-check anymore, so rely on the button label to confirm
  the date filter actually took.
- Flag anything that looks off and name the likely cause from the known failure modes:
  wrong `detect_y_offset` (clipped crop / wrong cards), sticky tab not cleared (wrong
  layout), or stale date coords (same extra metric keeps reappearing).
- Then **STOP and ask the user to confirm** ("lanjut insert?") before Step 3. If a brand's
  screenshot is wrong, offer to re-run just that brand before proceeding.

## Step 3 — Insert into Slides (only after user OK)

- Run `python3 insert_to_slides.py <BRANDS...>` for the **successful** brands only
  (exclude any NOT-FOUND brand like STRO-M).
- Parse the output per brand: template deck (1 slide added per brand), and each meeting deck
  (`12BCe2jv…` = "FBI Bottom Account", `1f2QVMCa…` = "FBI Bottom Account (13 Mei 2026)").
  Only the brand's **1-bulan** Shopee ROAS slide is replaced in the meeting decks; the
  3-bulan slide is left untouched by design.
  Note any **"No ROAS slides found … skipping"** — those need a manual check (the brand
  has no Shopee ROAS slide pair in that deck).

## Step 4 — Email report

- Send a **detailed per-deck** success report via the `send_email(subject, body)` function
  in `send_email.py` (NOT `send_success_report`, which is too generic and hides per-deck
  skips). Recipients come from `config.EMAIL_RECIPIENTS`.
- The body must list, explicitly: brands captured vs skipped (with reason, e.g. STRO-M not
  held), template-deck result, and per-meeting-deck results — surfacing every brand/deck
  combo that was skipped so the user knows exactly what to check or insert by hand.
- Subject like: `[Bottom Account Bot] Done — N/M brands, screenshots + Slides (<date>)`.

## Wrap-up

Give the user a short recap table (brand × screenshot × template × deck A × deck B) and
the list of manual-check items. Keep it tight.
