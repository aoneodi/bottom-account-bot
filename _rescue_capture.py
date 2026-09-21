"""One-off rescue capture for a brand whose Iklan page defeats the fixed scroll
(e.g. KENL-M: extra promo sections + slow load push Performa far below where
scroll_to_performa lands). Navigates from Pilih Toko exactly like the normal bot,
but scrolls ADAPTIVELY: small scroll steps, re-scanning for the two-row metric
card pattern after each, until the cards sit within the calibrated crop window.

Usage: python3 _rescue_capture.py BRAND
"""
import os
import subprocess
import sys
import time

import pyautogui
from PIL import Image

import shopee_ads_screenshot as bot
from config import SCREENSHOT_DIR

AKUN = sys.argv[1].upper() if len(sys.argv) > 1 else "KENL-M"
EXTRA_LOAD_WAIT = 10          # on top of click_iklan_shopee's built-in wait
MAX_SCROLL_STEPS = 24         # x2 ticks each = up to -48 ticks total
ACCEPT_MIN, ACCEPT_MAX = -80, 100  # acceptable offset range vs EXPECTED_CARD_TOP_Y


# Text-free right sides of the Jumlah Klik and ROAS cards. Real metric cards are
# a uniform grid, so their run tops align across columns; Rekomendasi cards don't.
VERIFY_COLS = (860, 1560)

# Alignment tolerance and verify-column run height, in LOGICAL px (were 12 and
# 130..230 screen px under the old Retina-2x assumption). The rest of the
# signature comes from the bot so both detectors re-tune from one place.
ALIGN_TOLERANCE = 6
VERIFY_RUN_LO, VERIFY_RUN_HI = 65, 115


def find_card_top():
    """detect_y_offset's algorithm, but returns the offset or None (no 0-on-fail
    ambiguity, no ±120 cap — the caller decides what offset is acceptable).

    2026-08-06 (NDRD-M): a candidate two-run pattern must also align with white
    runs at VERIFY_COLS — the Rekomendasi card row fakes the pattern at a single
    column and sat exactly in the accept window, ~400px above the real cards."""
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_rescue.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    img = Image.open(tmp_path)
    try:
        for x_logical in (500, 480, 520, 460):
            longs = [(s, l) for s, l in bot._white_runs(img, x_logical)
                     if l >= bot.CARD_RUN_MIN]
            for i in range(len(longs)):
                for j in range(i + 1, len(longs)):
                    pitch = longs[j][0] - longs[i][0]
                    if not (bot.CARD_PITCH_LO <= pitch <= bot.CARD_PITCH_HI
                            and bot.CARD_RUN_LO <= longs[i][1] <= bot.CARD_RUN_HI
                            and bot.CARD_RUN_LO <= longs[j][1] <= bot.CARD_RUN_HI):
                        continue
                    top = longs[i][0]
                    aligned = all(
                        any(abs(s - top) <= ALIGN_TOLERANCE
                            and VERIFY_RUN_LO <= l <= VERIFY_RUN_HI
                            for s, l in bot._white_runs(img, vx))
                        for vx in VERIFY_COLS)
                    if aligned:
                        return top - bot.EXPECTED_CARD_TOP_Y
        return None
    finally:
        os.remove(tmp_path)


def main():
    username = bot.BRANDS.get(AKUN)
    if not username:
        print(f"Brand '{AKUN}' not in brands.csv")
        sys.exit(1)

    print("=" * 50)
    print(f"RESCUE capture: {AKUN} ({username})")
    print("=" * 50)
    print("Starting in 10 seconds — be on Pilih Toko, then hands off!")
    for i in range(10, 0, -1):
        print(f"  ...{i}")
        time.sleep(1)

    print("  1. Searching for shop...")
    if not bot.search_and_verify(AKUN, username):
        print(f"  ⚠ '{AKUN}' not found — abort.")
        sys.exit(1)

    print("  2. Clicking Detail...")
    bot.click_first_detail()

    print("  3. Navigating to Iklan Shopee (extra-long wait for heavy page)...")
    bot.click_iklan_shopee(AKUN)
    time.sleep(EXTRA_LOAD_WAIT)

    print("  4. Popup check...")
    bot.close_popup()
    # 2026-08-06: new 'Aktifkan Optimasi pada Periode Promo' popup evades the
    # dimmed-overlay detection (close_popup logs "No popup detected"). Blind
    # Escapes are harmless when no popup is open, so always send two.
    pyautogui.press("esc")
    time.sleep(1)
    pyautogui.press("esc")
    time.sleep(1)

    print("  5. Adaptive scroll to the metric cards...")
    pyautogui.moveTo(855, 500)
    time.sleep(0.5)
    pyautogui.hotkey("command", "up")  # ensure we start from the very top
    time.sleep(2)

    offset = None
    for step in range(1, MAX_SCROLL_STEPS + 1):
        pyautogui.scroll(-2)
        time.sleep(1.2)
        off = find_card_top()
        if off is None:
            print(f"    step {step:2d}: cards not in view yet")
            continue
        print(f"    step {step:2d}: card pattern at offset {off:+d}")
        if off > ACCEPT_MAX:
            continue  # cards still too low — keep scrolling
        if off < ACCEPT_MIN:
            # overshot — nudge back up a tick at a time
            for _ in range(4):
                pyautogui.scroll(1)
                time.sleep(1.2)
                off = find_card_top()
                print(f"    nudge up: offset {'n/a' if off is None else f'{off:+d}'}")
                if off is not None and ACCEPT_MIN <= off <= ACCEPT_MAX:
                    break
        if off is not None and ACCEPT_MIN <= off <= ACCEPT_MAX:
            offset = off
            break

    if offset is None:
        dbg = os.path.join(SCREENSHOT_DIR, f"_dbg_rescue_fail_{AKUN}.png")
        subprocess.run(["screencapture", "-x", dbg])
        print(f"  ⚠ Never found the card pattern — debug shot: {dbg}")
        sys.exit(2)

    print(f"  6. Forcing 'Semua Iklan Produk' tab (offset-adjusted)...")
    pyautogui.click(bot.SEMUA_IKLAN_PRODUK_TAB[0],
                    bot.SEMUA_IKLAN_PRODUK_TAB[1] + offset)
    time.sleep(2)
    off = find_card_top()  # tab switch can change layout — re-detect
    if off is not None and ACCEPT_MIN <= off <= ACCEPT_MAX:
        offset = off
    print(f"    final offset: {offset:+d}")

    print("  7. Setting chart metrics (need: only Pengeluaran + ROAS)...")
    cards_adjusted = {name: (x, y + offset)
                      for name, (x, y) in bot.METRIC_CARDS.items()}
    for name, pos in cards_adjusted.items():
        selected = bot.is_card_selected(pos, debug_name=name)
        should_be = name in bot.DESIRED_SELECTED
        if selected and not should_be:
            print(f"    {name} is ON → clicking to deselect")
            pyautogui.click(*pos)
            time.sleep(1)
        elif not selected and should_be:
            print(f"    {name} is OFF → clicking to select")
            pyautogui.click(*pos)
            time.sleep(1)
        else:
            print(f"    {name} {'ON' if selected else 'OFF'} → OK")

    for filter_name in bot.DATE_FILTERS:  # just "1bulan" since 2026-09-16
        # 2026-08-06 (NDRD-M): lazy-loaded sections above Performa (Rekomendasi
        # cards) can finish rendering AFTER detection and push the cards ~500px
        # down, so the once-measured offset goes stale and every click/crop
        # lands on the wrong element. Re-verify before each filter pass.
        off = find_card_top()
        if off is None or not (ACCEPT_MIN <= off <= ACCEPT_MAX):
            print(f"    layout shifted (offset now "
                  f"{'n/a' if off is None else f'{off:+d}'}), re-settling...")
            time.sleep(3)  # let lazy content finish rendering
            for _ in range(MAX_SCROLL_STEPS):
                off = find_card_top()
                if off is not None and ACCEPT_MIN <= off <= ACCEPT_MAX:
                    break
                pyautogui.scroll(-2 if (off is None or off > ACCEPT_MAX) else 1)
                time.sleep(1.2)
            if off is None or not (ACCEPT_MIN <= off <= ACCEPT_MAX):
                dbg = os.path.join(SCREENSHOT_DIR, f"_dbg_rescue_shift_{AKUN}.png")
                subprocess.run(["screencapture", "-x", dbg])
                print(f"  ⚠ Could not re-settle after layout shift — debug shot: {dbg}")
                sys.exit(2)
            offset = off
            print(f"    re-settled at offset {offset:+d}, re-checking metrics...")
            for name, (x, y) in bot.METRIC_CARDS.items():
                pos = (x, y + offset)
                selected = bot.is_card_selected(pos, debug_name=name)
                if selected != (name in bot.DESIRED_SELECTED):
                    print(f"    {name} {'ON' if selected else 'OFF'} → clicking to fix")
                    pyautogui.click(*pos)
                    time.sleep(1)
        print(f"  8. Selecting '{filter_name}' filter (offset {offset:+d})...")
        bot.select_date_filter(filter_name, y_offset=offset)
        print(f"  9. Taking screenshot ({filter_name})...")
        bot.take_screenshot(AKUN, filter_name, y_offset=offset)

    print("  10. Going back to Pilih Toko...")
    bot.go_back_to_pilih_toko()
    print("DONE.")


if __name__ == "__main__":
    main()
