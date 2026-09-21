import pyautogui
import time
import subprocess
import os
import csv
import sys
import webbrowser
from datetime import datetime

import display
import popups
from config import (
    SELLER_CENTER_URL,
    SCREENSHOT_DIR,
    PAGE_LOAD_WAIT,
    CLICK_DELAY,
    SCROLL_DELAY,
    POPUP_WAIT,
    DATE_FILTERS,
)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

# Horizontal centre of the screen. Was hardcoded as 855 (= 1710/2, the old
# MacBook screen) at every moveTo; derived now so it follows the display.
SCREEN_CENTRE_X = pyautogui.size()[0] // 2

# Aspect ratio (width / height) the saved screenshot is padded to.
# insert_to_slides.py drops each new image into the OLD image's box on the
# meeting decks, so an image whose ratio differs from what those boxes were
# built for comes out stretched. On the 1920-wide monitor the Performa block is
# wider than it used to be (raw crop ≈3.01:1 vs the ≈2.56:1 the decks expect),
# so the crop is padded with white rather than squeezed. The page background
# around the crop edges is white, so the padding is seamless — and this keeps
# the decks correct on any future screen without touching hundreds of slides.
SCREENSHOT_ASPECT = 1407 / 550

# --- Coordinate map (pyautogui LOGICAL coords) ---
# Calibrated on the 1710x1112 MacBook screen. Every coord below is logical;
# conversion to screencapture pixels goes through `display` (see display.py),
# which measures the real scale at runtime instead of assuming Retina 2x.
# These values still need recalibrating for any screen of a different SIZE —
# `display` only fixes the scale, not the layout.
# Pilih Toko page
SEARCH_BOX = (735, 284)
FIRST_DETAIL_LINK = (1331, 495)

# Shop dashboard - sidebar
IKLAN_SHOPEE_MENU = (80, 739)

# Iklan Shopee page (positions after scrolling down)
SEMUA_IKLAN_PRODUK_TAB = (277, 398)
# Reference (MON-M, offset 0) date coords; the per-brand y_offset from detect_y_offset
# is added in select_date_filter so they track each brand's vertical shift.
# Button center y=446 (measured); option rows ~128/~160 px below the button center.
DATE_FILTER_DROPDOWN = (1349, 466)
FILTER_1BULAN = (850, 606)
FILTER_3BULAN = (850, 638)  # still calibrated, but unused unless "3bulan" is in config.DATE_FILTERS

# Metric cards (4 per row, evenly spaced)
# Row 1 (y=564): Tayangan, Produk Terjual, Jumlah Klik, Penjualan dari Iklan
# Row 2 (y=666): Persentase Klik, Pengeluaran, Pesanan, ROAS
# NOTE: Shopee renamed cards 2026-06: "Iklan Dilihat"->"Tayangan", "Biaya Iklan"->"Pengeluaran".
# Order/positions unchanged.
METRIC_CARDS = {
    # Recalibrated 2026-09-21 on the 1920x1080 Mi Monitor, measured from card
    # BORDERS in a live screencapture (rows y=499..582 and y=599..682; column
    # borders 222/606, 623/1007, 1024/1407, 1424/1808):
    # columns x=414/815/1215/1616 (≈401px apart), rows y=540/640 (pitch 100).
    # NOTE: this Shopee build labels the cards "Iklan Dilihat", "Penjualan" and
    # "Biaya Iklan" — the 2026-06 rename appears to have been reverted. Only the
    # POSITIONS matter here; the keys stay as-is so DESIRED_SELECTED still lines up.
    "Tayangan":              (414, 540),
    "Produk Terjual":        (414, 640),
    "Jumlah Klik":           (815, 540),
    "Penjualan dari Iklan":  (815, 640),
    "Persentase Klik":       (1215, 540),
    "Pengeluaran":           (1215, 640),
    "Pesanan":               (1616, 540),
    "ROAS":                  (1616, 640),
}
DESIRED_SELECTED = {"Pengeluaran", "ROAS"}


# Search filter dropdown
NAMA_TOKO_DROPDOWN = (470, 284)
USERNAME_TOKO_OPTION = (455, 361)

# Screenshot crop region (pyautogui coords)
CROP_TOP_LEFT = (209, 440)
CROP_BOTTOM_RIGHT = (1820, 975)

# Top-right account menu
ACCOUNT_BUTTON = (1645, 199)
GANTI_TOKO = (1486, 547)

# --- Brand list ---
BRANDS = {}
with open(os.path.join(os.path.dirname(__file__), "brands.csv")) as f:
    reader = csv.DictReader(f)
    for row in reader:
        BRANDS[row["akun"]] = row["shopee_username"]


def is_card_selected(card_pos, debug_name=None):
    """Check if a metric card is selected by scanning for a colored top border.
    Samples a wider strip above the card center to tolerate layout drift."""
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_detect.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)
    cx, cy = card_pos
    colored_count = 0
    best_sample = (0, 0, 0, 0, 0)  # (dy, dx, r, g, b)
    best_sat = 0
    # Scan up to 95px above center: row-2 cards (ROAS y=676, Penjualan y=660) sit
    # low enough that their colored top border lands at dy ≈ -72..-88 — just past
    # the old -70 limit, so selected cards there were missed and never deselected
    # (e.g. ALJA-M kept "Penjualan dari Iklan" on). The extra upward range only
    # samples whitespace/title above the cards (low saturation), so it doesn't add
    # false positives for cards that are actually off.
    for dy in range(-95, -4):
        for dx in range(-80, 81, 10):
            rgb = display.sample(img, cx + dx, cy + dy)
            if rgb is None:
                continue  # sample fell outside the capture — coords are stale
            r, g, b = rgb
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            saturation = (max_c - min_c) / max_c if max_c > 0 else 0
            if saturation > best_sat:
                best_sat = saturation
                best_sample = (dy, dx, r, g, b)
            if saturation > 0.25 and max_c > 100:
                colored_count += 1
    if debug_name:
        dy_b, dx_b, r, g, b = best_sample
        print(f"      [{debug_name}] colored={colored_count}, best_sat={best_sat:.2f} at dy={dy_b} dx={dx_b} rgb=({r},{g},{b})")
        # Save a debug crop centered on the card showing the sample region
        safe_name = debug_name.replace(" ", "_").replace("/", "_")
        dbg_path = os.path.join(SCREENSHOT_DIR, f"_dbg_{safe_name}.png")
        dbg_crop, _ = display.crop_logical(img, cx - 100, cy - 80, cx + 100, cy + 20)
        dbg_crop.save(dbg_path)
    os.remove(tmp_path)
    return colored_count >= 5


def notify(message):
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "Shopee Ads Bot"'
    ])


def pad_to_aspect(img, aspect=None):
    """Pad `img` with white until it has the given width/height ratio.

    Only ever ADDS white margin — never scales, stretches or crops — so the
    chart keeps its true proportions while the saved file matches the geometry
    insert_to_slides.py expects (see SCREENSHOT_ASPECT). Padding is centred, and
    white because the page background at the crop edges is white, making the
    seam invisible in the deck.
    """
    aspect = SCREENSHOT_ASPECT if aspect is None else aspect
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    target_h = round(w / aspect)
    target_w = round(h * aspect)
    if target_h >= h:
        new_w, new_h = w, target_h          # too wide -> add top/bottom margin
    else:
        new_w, new_h = target_w, h          # too tall -> add left/right margin
    if (new_w, new_h) == (w, h):
        return img
    from PIL import Image
    canvas = Image.new("RGB", (new_w, new_h), (255, 255, 255))
    canvas.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
    return canvas


def take_screenshot(brand_akun, filter_name, y_offset=0):
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{brand_akun}_{filter_name}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    # Park the pointer at a safe neutral spot (well above the cards, far from the
    # bottom screen edge) so the macOS auto-hide Dock doesn't slide up into the crop.
    # Some brands' flows leave the cursor near the bottom edge, which triggered the
    # Dock to appear in the captured image (seen on TAN-M). The 1.5s sleep below gives
    # the Dock time to retract before the screencapture.
    pyautogui.moveTo(SCREEN_CENTRE_X, 400)
    time.sleep(1.5)
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_full.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)
    cropped, clamped = display.crop_logical(
        img,
        CROP_TOP_LEFT[0],
        CROP_TOP_LEFT[1] + y_offset,
        CROP_BOTTOM_RIGHT[0],
        CROP_BOTTOM_RIGHT[1] + y_offset,
    )
    padded = pad_to_aspect(cropped)
    padded.save(filepath)
    os.remove(tmp_path)
    if padded.size != cropped.size:
        print(f"  Padded {cropped.width}x{cropped.height} -> "
              f"{padded.width}x{padded.height} to keep the deck's aspect ratio")
    if clamped:
        # The crop reached outside the capture. PIL pads that with black, so
        # without this the run would look successful and a part-black image
        # would land in both meeting decks. Loud, because it means CROP_* no
        # longer matches this display and needs --calibrate-crop.
        print(f"  ⚠ CROP OUT OF BOUNDS for {brand_akun} {filter_name}: wanted "
              f"{CROP_TOP_LEFT}-{CROP_BOTTOM_RIGHT} (+{y_offset}) but the capture "
              f"is {img.width}x{img.height}px. Image is padded/truncated — "
              f"re-run --calibrate-crop. DO NOT insert this into the decks.")
    print(f"  Saved: {filepath}")
    return filepath


def select_username_filter():
    pyautogui.click(*NAMA_TOKO_DROPDOWN)
    time.sleep(CLICK_DELAY)
    pyautogui.click(*USERNAME_TOKO_OPTION)
    time.sleep(CLICK_DELAY)


def search_shop(username):
    pyautogui.click(*SEARCH_BOX)
    time.sleep(CLICK_DELAY)
    pyautogui.hotkey("command", "a")
    time.sleep(0.2)
    pyautogui.typewrite(username, interval=0.03)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(PAGE_LOAD_WAIT)


def detail_link_present(akun=None, retries=2):
    """After searching on Pilih Toko, verify a result row with a blue 'Detail'
    link exists at FIRST_DETAIL_LINK.

    When the searched username isn't a shop we hold (e.g. STRO-M, which we don't
    have access to yet), Shopee returns an empty table with no Detail link. The
    old flow clicked the fixed Detail coord anyway (a no-op on empty space) and
    then navigated to the Iklan URL, which still showed whatever shop was
    previously selected — producing a screenshot of the WRONG brand. This guard
    detects the empty state so the brand is skipped instead.

    Retries to avoid false-negatives when a held account's page is just slow.
    On final failure, saves a full debug screenshot so we can see what the page
    actually showed (popup? empty table? wrong filter?).
    """
    from PIL import Image
    cx, cy = FIRST_DETAIL_LINK
    last_img = None
    for attempt in range(retries):
        tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_detail.png")
        subprocess.run(["screencapture", "-x", tmp_path])
        img = Image.open(tmp_path)
        last_img = img.copy()
        blue = 0
        for dy in range(-14, 15):
            for dx in range(-55, 56):
                rgb = display.sample(img, cx + dx, cy + dy)
                if rgb is None:
                    continue  # outside the capture — coords stale for this display
                r, g, b = rgb
                # Shopee link blue (~#2673dd): strong blue, weak red.
                if b > 170 and b - r > 60 and b - g > 30 and r < 140:
                    blue += 1
        os.remove(tmp_path)
        print(f"    Detail link blue pixels: {blue} (attempt {attempt + 1}/{retries})")
        if blue >= 10:
            return True
        if attempt < retries - 1:
            time.sleep(1.5)
    if last_img is not None:
        dbg = os.path.join(SCREENSHOT_DIR, f"_dbg_detail_fail_{akun or 'unknown'}.png")
        last_img.save(dbg)
        print(f"    [debug] saved failure screenshot: {dbg}")
    return False


def search_and_verify(akun, username, attempts=3):
    """Select the username filter, search, and verify a result row appeared.

    The search intermittently produces no result on longer runs — most likely a
    promo/ad popup on the Pilih Toko page eats the filter/search clicks, or the
    result is slow to render. Earlier this surfaced as VALID held accounts (SP,
    KSB-M) being skipped with blue=0 partway through a run. Rather than skip on
    the first empty result, this retries the WHOLE search (dismissing any popup
    with Escape first) up to `attempts` times. A genuinely-unheld account (e.g.
    STRO-M) fails every attempt and is still correctly skipped.

    Returns True if the 'Detail' link is detected, else False.
    """
    for attempt in range(attempts):
        # ROOT CAUSE (confirmed via debug screenshot): the previous brand's
        # go_back_to_pilih_toko intermittently fails — a popup on the Iklan page
        # intercepts the Cmd+L navigation — leaving us stuck on the PREVIOUS
        # brand's Iklan page. Then the filter/search clicks land on the wrong
        # page and the result never appears (blue=0). So each attempt explicitly
        # RE-NAVIGATES to Pilih Toko (go_back_to_pilih_toko dismisses popups with
        # Escape first) before selecting the filter and searching again.
        go_back_to_pilih_toko()
        select_username_filter()
        search_shop(username)
        if detail_link_present(akun):
            if attempt > 0:
                print(f"    Search succeeded on attempt {attempt + 1}/{attempts}")
            return True
        print(f"    No result on attempt {attempt + 1}/{attempts} — re-navigating + re-searching...")
    return False


def click_first_detail():
    pyautogui.click(*FIRST_DETAIL_LINK)
    time.sleep(PAGE_LOAD_WAIT)


def get_seller_domain(akun):
    if akun.startswith("TH."):
        return "seller.shopee.co.th"
    return "seller.shopee.co.id"


def click_iklan_shopee(akun):
    domain = get_seller_domain(akun)
    pyautogui.hotkey("command", "l")
    time.sleep(0.5)
    pyautogui.typewrite(f"https://{domain}/portal/marketing/pas/index", interval=0.01)
    time.sleep(0.3)
    pyautogui.press("enter")
    # Wait long enough for the page to load AND leave a generous ~15s window for the
    # user to manually close the "Bonus Eksklusif" popup (its light backdrop isn't
    # caught by is_popup_present, so it must be dismissed by hand). Mouse stays still
    # during this sleep, so the user's X-click won't fight the bot.
    time.sleep(PAGE_LOAD_WAIT + 15)


def is_popup_present():
    """Check if a dimmed overlay (popup backdrop) is visible."""
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_popup.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)
    sample_points = [(400, 900), (1400, 900), (400, 300)]
    dim_count = 0
    for x, y in sample_points:
        rgb = display.sample(img, x, y)
        if rgb is None:
            continue
        r, g, b = rgb
        if r < 80 and g < 80 and b < 80:
            dim_count += 1
    os.remove(tmp_path)
    return dim_count >= 2


def close_popup():
    time.sleep(POPUP_WAIT)

    # Registered popups first. is_popup_present() only sees a DIMMED backdrop,
    # so light-backdrop promo cards are invisible to it and Escape does not
    # close them anyway — they have an X. popups.dismiss() finds the card by
    # template match (tolerating the ~15px shift it drifts by) and clicks it.
    if popups.dismiss():
        time.sleep(CLICK_DELAY)

    # Then proper modals: a dimmed page with a dialog over it, closed by the X in
    # its top-right corner. is_popup_present() below only counts a backdrop as
    # dimmed at r,g,b < 80; the 2026-09-21 "Optimalkan Iklan" modal dimmed the
    # page to 142-153, was reported as "No popup detected", and every metric-card
    # click landed on the dialog — the run saved a screenshot of the wrong
    # metrics for ALUN-M. This check is generic, so it also covers modals that
    # are not registered individually.
    if popups.dismiss_modal():
        time.sleep(CLICK_DELAY)

    if not is_popup_present():
        print("    No popup detected, continuing...")
        return
    pyautogui.press("escape")
    time.sleep(CLICK_DELAY)
    if not is_popup_present():
        print("    Popup closed with Escape")
        return
    pyautogui.press("escape")
    time.sleep(CLICK_DELAY)
    if not is_popup_present():
        print("    Popup closed with second Escape")
        return
    # Unknown popup that Escape will not shift: capture it before handing over,
    # so it can be registered in popups.py and handled automatically next time.
    display.save_debug_shot("unknown_popup")
    print("    → Unrecognised popup. Add it to popups.py using that frame "
          "(see the ADDING A NEW POPUP notes there).")
    subprocess.run([
        "osascript", "-e",
        'display dialog "Popup still open — please close it, then click OK." with title "Shopee Ads Bot" buttons {"OK"} default button "OK" with icon caution'
    ])


def select_date_filter(filter_name, y_offset=0):
    pyautogui.moveTo(SCREEN_CENTRE_X, 400)
    time.sleep(0.5)
    pyautogui.click(DATE_FILTER_DROPDOWN[0], DATE_FILTER_DROPDOWN[1] + y_offset)
    time.sleep(2)
    if filter_name == "1bulan":
        pyautogui.click(FILTER_1BULAN[0], FILTER_1BULAN[1] + y_offset)
    else:
        pyautogui.click(FILTER_3BULAN[0], FILTER_3BULAN[1] + y_offset)
    time.sleep(PAGE_LOAD_WAIT + 2)


def scroll_to_performa():
    pyautogui.moveTo(SCREEN_CENTRE_X, 500)
    time.sleep(0.5)
    pyautogui.scroll(-7)
    time.sleep(SCROLL_DELAY)
    pyautogui.scroll(-8)
    time.sleep(SCROLL_DELAY)
    pyautogui.scroll(-3)
    time.sleep(2)


# Calibrated row-1 card top edge (logical y) on the reference brand (MON-M, offset 0).
# Used as anchor for auto-detect. Measured 2026-06-16 from a live full screencapture.
EXPECTED_CARD_TOP_Y = 500

# White-run signature of the two metric-card rows, all in LOGICAL px. These were
# previously written as screen px assuming Retina 2x (scan 400..1800, run >= 120,
# pitch 180..220, run 130..200); halving them gives the logical values below, which
# `display.px` converts back to whatever the current screen actually uses.
# _rescue_capture.py imports these so both detectors re-tune from one place.
CARD_SCAN_TOP_Y = 200           # start scanning below the page header
CARD_SCAN_BOTTOM_Y = 900        # stop before the chart/axis area
CARD_RUN_MIN = 60               # a run this long is a candidate card interior
CARD_RUN_LO, CARD_RUN_HI = 65, 100    # card interior height (~82 logical px)
CARD_PITCH_LO, CARD_PITCH_HI = 90, 110  # row1 top -> row2 top (~100 logical px)


def _white_runs(img, x_logical):
    """Vertical runs of white at a logical column, as (top, length) in LOGICAL px.

    Scans at the capture's native resolution and converts the results, so the
    scan keeps full precision on a Retina panel while the thresholds around it
    stay in one screen-independent unit.
    """
    x_screen = display.px(x_logical)
    if not (0 <= x_screen < img.width):
        return []
    y_start = max(0, display.px(CARD_SCAN_TOP_Y))
    y_end = min(display.px(CARD_SCAN_BOTTOM_Y), img.height)
    runs = []
    in_white = False
    white_start = None
    for y in range(y_start, y_end):
        r, g, b = img.getpixel((x_screen, y))[:3]
        is_white = r > 248 and g > 248 and b > 248
        if is_white and not in_white:
            in_white = True
            white_start = y
        elif not is_white and in_white:
            runs.append((display.to_logical(white_start),
                         display.to_logical(y - white_start)))
            in_white = False
    if in_white:
        runs.append((display.to_logical(white_start),
                     display.to_logical(y_end - white_start)))
    return runs


def detect_y_offset():
    """Scan for the actual top of row 1 cards and return offset from calibrated.
    Positive = cards lower than reference; negative = higher.

    Robust detection (rewritten 2026-06-16): the two metric-card rows each show a tall
    (~82 logical px) white interior, and their tops are exactly ~100 logical px apart
    (the row pitch). We scan a CLEAN white column inside the cards — the
    RIGHT portion of the Tayangan card, past the name/value text which broke the old
    scan at the card center — collect long white runs, and find the pair separated by
    the row pitch. The first run's top = row-1 card top. Whitespace above the cards has
    no pitch-matched partner, so it can't false-match (the old -217 bug).
    """
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_offset.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)

    # Try a few clean columns in the Tayangan card's white right portion (logical x).
    for x_logical in (500, 480, 520, 460):
        longs = [(s, l) for s, l in _white_runs(img, x_logical) if l >= CARD_RUN_MIN]
        for i in range(len(longs)):
            for j in range(i + 1, len(longs)):
                pitch = longs[j][0] - longs[i][0]
                if (CARD_PITCH_LO <= pitch <= CARD_PITCH_HI
                        and CARD_RUN_LO <= longs[i][1] <= CARD_RUN_HI
                        and CARD_RUN_LO <= longs[j][1] <= CARD_RUN_HI):
                    actual_top_logical = longs[i][0]
                    offset = actual_top_logical - EXPECTED_CARD_TOP_Y
                    if abs(offset) > 120:  # implausible — refuse rather than cascade
                        break
                    os.remove(tmp_path)
                    print(f"    Card top detected at logical y={actual_top_logical} "
                          f"(offset {offset:+d}, x={x_logical})")
                    return offset

    os.remove(tmp_path)
    print("    Could not detect card position, assuming offset=0")
    # Since the 2026-09-21 recalibration this path is NOT the normal case any
    # more (it used to fire on every brand), so reaching it means something is
    # genuinely off — a popup over the cards, a layout shift, a half-loaded
    # page. Keep the frame; offset=0 may well produce a wrong crop.
    display.save_debug_shot("offset_detect_failed")
    return 0


def go_back_to_pilih_toko(akun=None):
    # Dismiss any popup on the current (Iklan) page first — a popup has been seen
    # to intercept the Cmd+L navigation and leave the bot stuck on the previous
    # brand's page, which then cascades into wrong/empty searches for every
    # subsequent brand. Two Escapes for popups that need a second dismiss.
    pyautogui.press("escape")
    time.sleep(0.3)
    pyautogui.press("escape")
    time.sleep(0.3)
    pyautogui.hotkey("command", "l")
    time.sleep(0.5)
    pyautogui.typewrite("https://seller.shopee.co.id/portal/shop", interval=0.01)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(PAGE_LOAD_WAIT)


def process_brand(akun):
    username = BRANDS.get(akun)
    if not username:
        print(f"  Brand '{akun}' not found in brands.csv, skipping.")
        return []

    print(f"\n{'='*50}")
    print(f"Processing: {akun} ({username})")
    print(f"{'='*50}")

    screenshots = []

    print("  1-2. Searching for shop (filter + search + verify, with retries)...")
    if not search_and_verify(akun, username):
        print(f"  ⚠ '{akun}' not found on Pilih Toko after retries — account likely "
              f"not held. Skipping to avoid screenshotting the previously-selected shop.")
        return None

    print("  3. Clicking Detail...")
    click_first_detail()

    print("  4. Navigating to Iklan Shopee...")
    click_iklan_shopee(akun)

    print("  5. Closing popup...")
    close_popup()

    print("  7. Scrolling to Performa section...")
    scroll_to_performa()

    print("  7a. Forcing 'Semua Iklan Produk' tab...")
    pyautogui.click(*SEMUA_IKLAN_PRODUK_TAB)
    time.sleep(2)

    print("  7b. Detecting card position offset...")
    y_offset = detect_y_offset()

    cards_adjusted = {name: (x, y + y_offset) for name, (x, y) in METRIC_CARDS.items()}

    print("  8. Setting chart metrics (need: only Pengeluaran + ROAS)...")
    for name, pos in cards_adjusted.items():
        selected = is_card_selected(pos, debug_name=name)
        should_be = name in DESIRED_SELECTED
        if selected and not should_be:
            print(f"    {name} is ON → clicking to deselect")
            pyautogui.click(*pos)
            time.sleep(1)
        elif not selected and should_be:
            print(f"    {name} is OFF → clicking to select")
            pyautogui.click(*pos)
            time.sleep(1)
        else:
            status = "ON" if selected else "OFF"
            print(f"    {name} {status} → OK")

    # Verify the toggles actually took. A click that misses (stale coords, a
    # popup swallowing it, the page reflowing mid-loop) leaves the chart showing
    # the wrong metrics, and the screenshot still looks plausible — so the wrong
    # chart would go into both decks unnoticed. Check, and keep the frame.
    wrong = [n for n, pos in cards_adjusted.items()
             if is_card_selected(pos) != (n in DESIRED_SELECTED)]
    if wrong:
        print(f"  ⚠ METRICS NOT AS REQUESTED for {akun}: {', '.join(wrong)} "
              f"still wrong after toggling (want only "
              f"{', '.join(sorted(DESIRED_SELECTED))}).")
        display.save_debug_shot(f"metrics_{akun}")
    else:
        print(f"    Verified: only {', '.join(sorted(DESIRED_SELECTED))} selected")

    # Only the filters in config.DATE_FILTERS (just "1bulan" since 2026-09-16).
    for filter_name in DATE_FILTERS:
        label = "1 bulan" if filter_name == "1bulan" else "3 bulan"

        print(f"  7. Selecting '{label}' filter...")
        select_date_filter(filter_name, y_offset=y_offset)

        print(f"  8. Taking screenshot ({filter_name})...")
        path = take_screenshot(akun, filter_name, y_offset=y_offset)
        screenshots.append(path)

    print("  9. Going back to Pilih Toko...")
    go_back_to_pilih_toko()

    return screenshots


def calibrate():
    """Interactive calibration mode - move mouse to each element."""
    print("\n=== CALIBRATION MODE ===")
    print("I'll guide you to hover over elements so we can record positions.")
    print("For each element, move your mouse there and press ENTER.\n")

    elements = [
        ("SEARCH_BOX", "the 'Cari' search input on Pilih Toko page"),
        ("FIRST_DETAIL_LINK", "the first 'Detail' link in the table"),
        ("IKLAN_SHOPEE_MENU", "'Iklan Shopee' in the left sidebar (enter a shop first)"),
        ("DATE_FILTER_DROPDOWN", "the date filter dropdown (e.g. '3 bulan terakhir')"),
        ("FILTER_1BULAN", "'1 bulan terakhir' option (open dropdown first)"),
        ("FILTER_3BULAN", "'3 bulan terakhir' option (open dropdown first)"),
        ("ACCOUNT_BUTTON", "the account/shop name at top-right"),
        ("GANTI_TOKO", "'Ganti toko' in the dropdown"),
    ]

    results = {}
    for name, desc in elements:
        input(f"Hover over {desc}, then press ENTER...")
        pos = pyautogui.position()
        results[name] = (pos.x, pos.y)
        print(f"  {name} = ({pos.x}, {pos.y})")

    print("\n=== Copy these into shopee_ads_screenshot.py ===")
    for name, (x, y) in results.items():
        print(f"{name} = ({x}, {y})")


def calibrate_cards():
    """Re-record the 8 metric card positions on the Iklan Shopee page."""
    print("\n=== METRIC CARDS CALIBRATION ===")
    subprocess.run([
        "osascript", "-e",
        'display dialog "Navigate to Iklan Shopee page, scroll so all 8 metric cards are visible. Click OK to start." with title "Calibrate Cards" buttons {"OK"} default button "OK"'
    ])

    card_names = [
        "Tayangan", "Produk Terjual", "Jumlah Klik", "Penjualan dari Iklan",
        "Persentase Klik", "Pengeluaran", "Pesanan", "ROAS",
    ]
    results = {}
    for name in card_names:
        subprocess.run([
            "osascript", "-e",
            f'display dialog "Click OK then hover the CENTER of the \'{name}\' card within 5 seconds." with title "Calibrate Cards" buttons {{"OK"}} default button "OK"'
        ])
        time.sleep(5)
        pos = pyautogui.position()
        results[name] = (pos.x, pos.y)
        print(f"  {name} = ({pos.x}, {pos.y})")

    print("\n=== Paste into METRIC_CARDS in shopee_ads_screenshot.py ===")
    print("METRIC_CARDS = {")
    for name, (x, y) in results.items():
        print(f'    "{name}":{" " * (22 - len(name))}({x}, {y}),')
    print("}")


def calibrate_crop():
    """Re-record the screenshot crop region (Performa section)."""
    print("\n=== SCREENSHOT CROP CALIBRATION ===")
    subprocess.run([
        "osascript", "-e",
        'display dialog "Navigate to Iklan Shopee page, scroll so cards + chart + date axis are all visible. Click OK to start." with title "Calibrate Crop" buttons {"OK"} default button "OK"'
    ])

    subprocess.run([
        "osascript", "-e",
        'display dialog "Click OK then hover the TOP-LEFT corner of the area to capture within 5 seconds." with title "Calibrate Crop" buttons {"OK"} default button "OK"'
    ])
    time.sleep(5)
    tl = pyautogui.position()
    print(f"  TOP-LEFT = ({tl.x}, {tl.y})")

    subprocess.run([
        "osascript", "-e",
        'display dialog "Click OK then hover the BOTTOM-RIGHT corner (below the date axis) within 5 seconds." with title "Calibrate Crop" buttons {"OK"} default button "OK"'
    ])
    time.sleep(5)
    br = pyautogui.position()
    print(f"  BOTTOM-RIGHT = ({br.x}, {br.y})")

    print("\n=== Paste into shopee_ads_screenshot.py ===")
    print(f"CROP_TOP_LEFT = ({tl.x}, {tl.y})")
    print(f"CROP_BOTTOM_RIGHT = ({br.x}, {br.y})")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--calibrate":
        calibrate()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--calibrate-cards":
        calibrate_cards()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--calibrate-crop":
        calibrate_crop()
        return

    if len(sys.argv) >= 2:
        brand_list = [b.strip().upper() for b in sys.argv[1:]]
    else:
        from read_brands_from_sheet import fetch_bottom_brands
        print("No brands specified — fetching from Google Sheet...")
        brand_list = fetch_bottom_brands()
        brand_list = [b for b in brand_list if b in BRANDS]
        if not brand_list:
            print("No brands found in sheet (or none matched brands.csv).")
            sys.exit(1)
        print(f"Found {len(brand_list)} brands: {', '.join(brand_list)}")

    invalid = [b for b in brand_list if b not in BRANDS]
    if invalid:
        print(f"Unknown brands: {', '.join(invalid)}")
        print(f"Available: {', '.join(sorted(BRANDS.keys()))}")
        sys.exit(1)

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("=" * 50)
    print("Shopee Ads Screenshot Bot")
    print(f"Brands: {', '.join(brand_list)}")
    print("=" * 50)

    countdown = 10
    print(f"Starting in {countdown} seconds — switch to Shopee 'Pilih Toko' now!")
    for i in range(countdown, 0, -1):
        print(f"  ...{i}")
        time.sleep(1)

    all_screenshots = {}
    not_found = []
    for akun in brand_list:
        screenshots = process_brand(akun)
        if screenshots:
            all_screenshots[akun] = screenshots
        elif screenshots is None:
            not_found.append(akun)

    print("\n" + "=" * 50)
    print("DONE! Screenshots saved:")
    for akun, paths in all_screenshots.items():
        print(f"  {akun}:")
        for p in paths:
            print(f"    - {p}")
    if not_found:
        print("\n⚠ NOT FOUND (skipped — account not held / no search result):")
        for akun in not_found:
            print(f"    - {akun}")
        print("  → Verify these manually; no screenshot was taken.")
    print("=" * 50)

    msg = "All screenshots done!"
    if not_found:
        msg += f" Skipped (not found): {', '.join(not_found)}"
    notify(msg)
    return all_screenshots


if __name__ == "__main__":
    main()
