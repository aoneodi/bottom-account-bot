"""Pre-run check: put the screen into the state the calibration assumes, and
say whether the Shopee session is still alive.

The bot drives the real mouse against hardcoded coordinates, so a scheduled run
that starts blind will either fail or — worse — click through a login page and
produce junk. This runs first and answers one question with an exit code:

    0  ready   — Chrome is up, geometry matches the calibration, session alive,
                 sitting on Pilih Toko.
    1  not logged in — session expired (needs the user's CAPTCHA/OTP).
    2  error   — Chrome missing, navigation failed, page never rendered.

It also *enforces* the geometry rather than just checking it, because the
2026-09-21 calibration is only valid for one window size with the Dock hidden
(see CLAUDE.md "Environment the calibration assumes"). A window someone
resized yesterday would otherwise silently shift every click.

Usage:  python3 preflight.py [--quiet]
"""
import subprocess
import sys
import time

import display

PILIH_TOKO_URL = "https://seller.shopee.co.id/portal/shop"
WINDOW_BOUNDS = (0, 25, 1920, 1080)   # macOS clamps the top to below the menu bar
PAGE_WAIT = 9


def _osa(script):
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def frontmost():
    rc, out, _ = _osa('tell application "System Events" to get name of '
                      'first process whose frontmost is true')
    return out


def bring_to_front(log=print, tries=3):
    """Activate Chrome and CONFIRM it actually came forward.

    Without this check a capture can show whatever window was really on top,
    and the shop table then reads as missing — which the caller would report as
    "session expired" and email the user to log in, when nothing is wrong with
    the session at all. Seen 2026-09-21: the editor held the front and preflight
    flipped from exit 0 to exit 1 between two runs minutes apart.
    """
    for attempt in range(1, tries + 1):
        _osa('tell application "Google Chrome" to activate')
        time.sleep(1.5 * attempt)
        who = frontmost()
        if who == "Google Chrome":
            return True
        log(f"  preflight: front window is {who!r}, not Chrome "
            f"(attempt {attempt}/{tries})")
    return False


def chrome_running():
    rc, out, _ = _osa('tell application "System Events" to '
                      '(name of processes) contains "Google Chrome"')
    return out == "true"


def ensure_geometry(log=print):
    """Chrome frontmost, calibrated window size, Dock out of the way."""
    if not chrome_running():
        log("  preflight: Chrome is not running — launching it")
        subprocess.run(["open", "-a", "Google Chrome"])
        time.sleep(6)
        if not chrome_running():
            return False

    # The Dock eats 90px off the bottom of the screen when it is pinned, which
    # is more than the crop's spare room. Auto-hide is part of the calibration.
    rc, out, _ = _osa('do shell script "defaults read com.apple.dock autohide"')
    if out != "1":
        log("  preflight: Dock was pinned — switching it to auto-hide")
        subprocess.run(["defaults", "write", "com.apple.dock", "autohide",
                        "-bool", "true"])
        subprocess.run(["killall", "Dock"])
        time.sleep(3)

    if not bring_to_front(log):
        log("  preflight: could not bring Chrome to the front — another app is "
            "holding it. NOT treating this as a login problem.")
        return False
    l, t, r, b = WINDOW_BOUNDS
    _osa(f'tell application "Google Chrome" to set bounds of window 1 '
         f'to {{{l}, {t}, {r}, {b}}}')
    time.sleep(1)
    rc, out, _ = _osa('tell application "Google Chrome" to get bounds of window 1')
    log(f"  preflight: Chrome window bounds {out}")
    return True


def goto_pilih_toko(log=print):
    """Navigate the front tab to Pilih Toko. Returns the URL that came back."""
    _osa(f'tell application "Google Chrome" to set URL of active tab of '
         f'window 1 to "{PILIH_TOKO_URL}"')
    time.sleep(PAGE_WAIT)
    rc, url, _ = _osa('tell application "Google Chrome" to get URL of '
                      'active tab of window 1')
    log(f"  preflight: landed on {url}")
    return url


def shop_table_visible():
    """True if the shop list rendered — many blue 'Detail' links down column Aksi.

    Checked by pixels rather than by URL alone: Shopee can serve the Pilih Toko
    URL and then render an interstitial, and a URL check would call that a pass.
    """
    from PIL import Image
    import os
    from config import SCREENSHOT_DIR
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    tmp = os.path.join(SCREENSHOT_DIR, "_tmp_preflight.png")
    subprocess.run(["screencapture", "-x", tmp])
    img = Image.open(tmp); img.load()
    os.remove(tmp)
    blue = 0
    for y in range(450, 1020, 3):
        for x in range(1280, 1380, 2):
            rgb = display.sample(img, x, y)
            if rgb is None:
                continue
            r, g, b = rgb
            if b > 170 and b - r > 60 and b - g > 30 and r < 140:
                blue += 1
    return blue


def main():
    quiet = "--quiet" in sys.argv
    log = (lambda *a, **k: None) if quiet else print

    if not ensure_geometry(log):
        log("  preflight: could not bring Chrome up")
        return 2

    url = goto_pilih_toko(log)
    if "/portal/shop" not in url:
        # Shopee bounces unauthenticated requests to the sign-in flow.
        log("  preflight: redirected away from Pilih Toko -> session expired")
        return 1

    # Re-confirm Chrome owns the screen right before the capture: navigation
    # takes ~9s, and anything that grabs focus in that window would otherwise
    # be captured instead of the shop list.
    who = frontmost()
    if who != "Google Chrome":
        log(f"  preflight: {who!r} took the front before the capture — "
            f"environment problem, not a login problem")
        return 2

    blue = shop_table_visible()
    log(f"  preflight: {blue} blue pixels in the Aksi column")
    if blue < 30:
        log("  preflight: shop table did not render -> treating as not logged in")
        return 1

    log("  preflight: READY — session alive, on Pilih Toko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
