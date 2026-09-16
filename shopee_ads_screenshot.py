import pyautogui
import time
import subprocess
import os
import csv
import sys
import webbrowser
from datetime import datetime

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

# --- Coordinate map (pyautogui coords for 1710x1112 screen) ---
# Pilih Toko page
SEARCH_BOX = (488, 328)
FIRST_DETAIL_LINK = (1216, 535)

# Shop dashboard - sidebar
IKLAN_SHOPEE_MENU = (80, 739)

# Iklan Shopee page (positions after scrolling down)
SEMUA_IKLAN_PRODUK_TAB = (280, 430)
# Reference (MON-M, offset 0) date coords; the per-brand y_offset from detect_y_offset
# is added in select_date_filter so they track each brand's vertical shift.
# Button center y=446 (measured); option rows ~128/~160 px below the button center.
DATE_FILTER_DROPDOWN = (1110, 446)
FILTER_1BULAN = (662, 574)
FILTER_3BULAN = (662, 606)  # still calibrated, but unused unless "3bulan" is in config.DATE_FILTERS

# Metric cards (4 per row, evenly spaced)
# Row 1 (y=564): Tayangan, Produk Terjual, Jumlah Klik, Penjualan dari Iklan
# Row 2 (y=666): Persentase Klik, Pengeluaran, Pesanan, ROAS
# NOTE: Shopee renamed cards 2026-06: "Iklan Dilihat"->"Tayangan", "Biaya Iklan"->"Pengeluaran".
# Order/positions unchanged.
METRIC_CARDS = {
    # Measured 2026-06-11 from a live full screencapture (uniform grid, not hover):
    # columns x=390/742/1094/1446 (≈352px apart), rows y=512/612.
    "Tayangan":              (390, 512),
    "Produk Terjual":        (390, 612),
    "Jumlah Klik":           (742, 512),
    "Penjualan dari Iklan":  (742, 612),
    "Persentase Klik":       (1094, 512),
    "Pengeluaran":           (1094, 612),
    "Pesanan":               (1446, 512),
    "ROAS":                  (1446, 612),
}
DESIRED_SELECTED = {"Pengeluaran", "ROAS"}


# Search filter dropdown
NAMA_TOKO_DROPDOWN = (386, 322)
USERNAME_TOKO_OPTION = (394, 401)

# Screenshot crop region (pyautogui coords)
CROP_TOP_LEFT = (209, 413)
CROP_BOTTOM_RIGHT = (1616, 963)

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
            px_x = (cx + dx) * 2
            px_y = (cy + dy) * 2
            r, g, b = img.getpixel((px_x, px_y))[:3]
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
        crop_box = (
            max(0, (cx - 100) * 2),
            max(0, (cy - 80) * 2),
            min(img.width, (cx + 100) * 2),
            min(img.height, (cy + 20) * 2),
        )
        img.crop(crop_box).save(dbg_path)
    os.remove(tmp_path)
    return colored_count >= 5


def notify(message):
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "Shopee Ads Bot"'
    ])


def take_screenshot(brand_akun, filter_name, y_offset=0):
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{brand_akun}_{filter_name}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    # Park the pointer at a safe neutral spot (well above the cards, far from the
    # bottom screen edge) so the macOS auto-hide Dock doesn't slide up into the crop.
    # Some brands' flows leave the cursor near the bottom edge, which triggered the
    # Dock to appear in the captured image (seen on TAN-M). The 1.5s sleep below gives
    # the Dock time to retract before the screencapture.
    pyautogui.moveTo(855, 400)
    time.sleep(1.5)
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_full.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)
    x1 = CROP_TOP_LEFT[0] * 2
    y1 = (CROP_TOP_LEFT[1] + y_offset) * 2
    x2 = CROP_BOTTOM_RIGHT[0] * 2
    y2 = (CROP_BOTTOM_RIGHT[1] + y_offset) * 2
    cropped = img.crop((x1, y1, x2, y2))
    cropped.save(filepath)
    os.remove(tmp_path)
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
                r, g, b = img.getpixel(((cx + dx) * 2, (cy + dy) * 2))[:3]
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
        r, g, b = img.getpixel((x * 2, y * 2))[:3]
        if r < 80 and g < 80 and b < 80:
            dim_count += 1
    os.remove(tmp_path)
    return dim_count >= 2


def close_popup():
    time.sleep(POPUP_WAIT)
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
    subprocess.run([
        "osascript", "-e",
        'display dialog "Popup still open — please close it, then click OK." with title "Shopee Ads Bot" buttons {"OK"} default button "OK" with icon caution'
    ])


def select_date_filter(filter_name, y_offset=0):
    pyautogui.moveTo(855, 400)
    time.sleep(0.5)
    pyautogui.click(DATE_FILTER_DROPDOWN[0], DATE_FILTER_DROPDOWN[1] + y_offset)
    time.sleep(2)
    if filter_name == "1bulan":
        pyautogui.click(FILTER_1BULAN[0], FILTER_1BULAN[1] + y_offset)
    else:
        pyautogui.click(FILTER_3BULAN[0], FILTER_3BULAN[1] + y_offset)
    time.sleep(PAGE_LOAD_WAIT + 2)


def scroll_to_performa():
    pyautogui.moveTo(855, 500)
    time.sleep(0.5)
    pyautogui.scroll(-7)
    time.sleep(SCROLL_DELAY)
    pyautogui.scroll(-8)
    time.sleep(SCROLL_DELAY)
    pyautogui.scroll(-3)
    time.sleep(2)


# Calibrated row-1 card top edge (logical y) on the reference brand (MON-M, offset 0).
# Used as anchor for auto-detect. Measured 2026-06-16 from a live full screencapture.
EXPECTED_CARD_TOP_Y = 471


def detect_y_offset():
    """Scan for the actual top of row 1 cards and return offset from calibrated.
    Positive = cards lower than reference; negative = higher.

    Robust detection (rewritten 2026-06-16): the two metric-card rows each show a tall
    (~164 screen px) white interior, and their tops are exactly ~200 screen px apart
    (the 100-logical row pitch). We scan a CLEAN white column inside the cards — the
    RIGHT portion of the Tayangan card, past the name/value text which broke the old
    scan at the card center — collect long white runs, and find the pair separated by
    the row pitch. The first run's top = row-1 card top. Whitespace above the cards has
    no pitch-matched partner, so it can't false-match (the old -217 bug).
    """
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_offset.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    from PIL import Image
    img = Image.open(tmp_path)
    _, height = img.size

    # Try a few clean columns in the Tayangan card's white right portion (logical x).
    for x_logical in (500, 480, 520, 460):
        x_screen = x_logical * 2
        runs = []
        in_white = False
        white_start = None
        for y in range(400, min(1800, height)):
            r, g, b = img.getpixel((x_screen, y))[:3]
            is_white = r > 248 and g > 248 and b > 248
            if is_white and not in_white:
                in_white = True
                white_start = y
            elif not is_white and in_white:
                runs.append((white_start, y, y - white_start))
                in_white = False
        if in_white:
            runs.append((white_start, min(1800, height), min(1800, height) - white_start))

        # Card interiors are ~164 screen px tall; row1/row2 tops are ~200 screen px apart.
        longs = [(s, e, l) for s, e, l in runs if l >= 120]
        for i in range(len(longs)):
            for j in range(i + 1, len(longs)):
                pitch = longs[j][0] - longs[i][0]
                if 180 <= pitch <= 220 and 130 <= longs[i][2] <= 200 and 130 <= longs[j][2] <= 200:
                    actual_top_logical = longs[i][0] // 2
                    offset = actual_top_logical - EXPECTED_CARD_TOP_Y
                    if abs(offset) > 120:  # implausible — refuse rather than cascade
                        break
                    os.remove(tmp_path)
                    print(f"    Card top detected at logical y={actual_top_logical} "
                          f"(offset {offset:+d}, x={x_logical})")
                    return offset

    os.remove(tmp_path)
    print("    Could not detect card position, assuming offset=0")
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
