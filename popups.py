"""Known blocking popups, and how to recognise and dismiss them.

Why this exists: `shopee_ads_screenshot.is_popup_present()` only spots a popup
by its **dimmed dark backdrop** (r,g,b < 80 at three sample points). Plenty of
Shopee's popups have a LIGHT backdrop and are completely invisible to it —
verified 2026-09-21 on the "Rekomendasi Iklan" promo card, where all three
sample points read pure white while the card was plainly on screen. CLAUDE.md
records two more that slipped through the same way ("Bonus Eksklusif",
"Aktifkan Optimasi pada Periode Promo"), and the workaround so far has been a
15-second pause for the user to close it by hand plus blind Escapes.

Escape does not close these promo cards either — they have an X that must be
clicked. So each known popup is registered here with a colour signature and a
close target, both measured from a real screencapture.

ADDING A NEW POPUP (one screenshot is enough):
  1. When a run gets stuck, grab the frame: `python3 popups.py --capture`
     (or use the `_dbg_*.png` the bot saves on an anomaly).
  2. Pick 2-3 sample points that are distinctive while the popup is up and
     read as plain page background when it is gone — a saturated brand colour
     is ideal. Note their logical (x, y) and RGB.
  3. Measure the X: find its glyph and take the centre of its bounding box.
     VERIFY IT by drawing a marker at the coordinate and looking at the image —
     text strokes share the X's grey and it is easy to land on a letter instead.
  4. Append an entry below.

All coordinates are LOGICAL (pyautogui) px, converted for pixel reads by
`display`, so entries stay valid across displays of different scale. They are
NOT valid across a different window size — see CLAUDE.md "Coordinates".
"""
import os
import subprocess
import time

import pyautogui

import display

KNOWN_POPUPS = [
    {
        "name": "Rekomendasi Iklan promo card",
        # Top-right floating card: "Tingkatkan penjualan dan performa iklan
        # kamu dengan Halaman Rekomendasi Iklan! Coba sekarang" + "Buka".
        # Seen on Pilih Toko, 2026-09-21. Intermittent — gone minutes later on
        # the same page, which is why it is registered rather than handled ad hoc.
        "template": "popup_rekomendasi_iklan_buka.png",  # the orange "Buka" button
        "search": (1450, 150, 1900, 340),   # left, top, right, bottom to scan
        "threshold": 18.0,                  # max mean abs channel difference
        "close_offset": (37, -55),          # X, relative to the template's top-left
    },
]

REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_images")
_templates = {}


def _capture():
    """Grab the current screen as a PIL image (the temp file is not kept)."""
    from PIL import Image
    from config import SCREENSHOT_DIR
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, "_tmp_popup_scan.png")
    subprocess.run(["screencapture", "-x", path])
    img = Image.open(path)
    img.load()
    os.remove(path)
    return img


def _template(name):
    from PIL import Image
    if name not in _templates:
        import numpy as np
        img = Image.open(os.path.join(REF_DIR, name)).convert("RGB")
        _templates[name] = np.asarray(img, dtype=np.int16)
    return _templates[name]


def _match(img, spec):
    """Locate a popup by template match. Returns (score, (x, y)) or None.

    Fixed sample points were tried first and failed both ways: the card shifts
    by ~15px between frames (so a known-present popup scored 1/3), and Shopee's
    pages are full of the same orange (so the Iklan page scored 2/3 with no
    popup at all). Matching a distinctive patch inside a search window fixes
    both — it tolerates the shift and is specific enough not to fire on
    unrelated brand colour.

    Coordinates in and out are LOGICAL; the frame is sampled at whatever scale
    the display reports.
    """
    import numpy as np
    tpl = _template(spec["template"])
    th, tw = tpl.shape[:2]

    scale = display.scale()
    frame = np.asarray(img.convert("RGB"), dtype=np.int16)
    if scale != 1.0:
        # Work in logical space so templates stay display-independent.
        from PIL import Image
        lw, lh = round(img.width / scale), round(img.height / scale)
        frame = np.asarray(img.convert("RGB").resize((lw, lh), Image.BILINEAR),
                           dtype=np.int16)

    l, t, r, b = spec["search"]
    l, t = max(0, l), max(0, t)
    r, b = min(frame.shape[1], r), min(frame.shape[0], b)
    if r - l < tw or b - t < th:
        return None

    best = None

    # Coarse pass on a grid, then refine around the winner — a full per-pixel
    # scan of this window is ~76k positions and needlessly slow.
    def scan(y0, y1, x0, x1, step):
        nonlocal best
        for y in range(y0, y1 + 1, step):
            for x in range(x0, x1 + 1, step):
                window = frame[y:y + th, x:x + tw]
                score = float(np.abs(window - tpl).mean())
                if best is None or score < best[0]:
                    best = (score, (x, y))

    scan(t, b - th, l, r - tw, 4)
    if best is None:
        return None
    bx, by = best[1]
    scan(max(t, by - 4), min(b - th, by + 4), max(l, bx - 4), min(r - tw, bx + 4), 1)
    return best


def identify(img=None):
    """Return (spec, score, close_target) for a registered popup on screen, else None."""
    img = _capture() if img is None else img
    for spec in KNOWN_POPUPS:
        found = _match(img, spec)
        if found is None:
            continue
        score, (x, y) = found
        if score <= spec["threshold"]:
            dx, dy = spec["close_offset"]
            return spec, score, (x + dx, y + dy)
    return None


# --- Generic modal handling -------------------------------------------------
# A registry entry is needed only for popups with no dimmed backdrop (the
# floating promo cards). Proper modals share a structure worth handling once:
# the page behind them is dimmed to a flat grey, the dialog is a bright card,
# and it closes with an X near its top-right corner.
#
# The old is_popup_present() in shopee_ads_screenshot.py looks for r,g,b < 80,
# which is far too strict: the "Optimalkan Iklan" modal (2026-09-21, ALUN-M)
# dimmed the page to 142-153 and was reported as "No popup detected", so every
# card click landed on the dialog and the run produced a screenshot of the
# wrong metrics.

DIM_SAMPLES = [(300, 760), (300, 300), (1750, 760), (1750, 300), (960, 1010)]
DIM_LO, DIM_HI = 60, 215      # a dimmed page, vs ~245-255 undimmed
DIM_NEUTRAL = 14              # r/g/b spread — an overlay greys uniformly


def backdrop_dimmed(img, min_hits=3):
    """True if the page behind looks covered by a modal scrim."""
    hits = 0
    for x, y in DIM_SAMPLES:
        rgb = display.sample(img, x, y)
        if rgb is None:
            continue
        r, g, b = rgb
        if DIM_LO <= max(r, g, b) <= DIM_HI and (max(rgb) - min(rgb)) <= DIM_NEUTRAL:
            hits += 1
    return hits >= min_hits


def modal_box(img):
    """Bounding box of the bright dialog sitting on the dimmed page."""
    import numpy as np
    scale = display.scale()
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    if scale != 1.0:
        from PIL import Image
        a = np.asarray(img.convert("RGB").resize(
            (round(img.width / scale), round(img.height / scale)),
            Image.BILINEAR), dtype=np.int16)
    bright = (a.min(axis=2) > 235)
    rows = np.where(bright.sum(axis=1) > 150)[0]
    cols = np.where(bright.sum(axis=0) > 150)[0]
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


def find_close_x(img, box, margin=90):
    """Centre of the X glyph in the dialog's top-right corner, or None.

    Constrained to that corner of a confirmed modal, so it cannot wander off and
    click something else — the failure mode that makes a free-roaming glyph hunt
    too risky on its own.

    Candidate pixels are CLUSTERED before being judged. Taking the bounding box
    of every grey pixel in the corner does not work: on the 2026-09-21 "Optimalkan
    Iklan" modal a single stray pixel on the dialog's rounded corner stretched the
    box from the glyph's true 12x12 to 41x42, and the shape test threw the real X
    away.
    """
    l, t, r, b = box
    pts = set()
    for y in range(t, min(t + margin, b)):
        for x in range(max(l, r - margin), r):
            rgb = display.sample(img, x, y)
            if rgb is None:
                continue
            cr, cg, cb = rgb
            if 90 < cr < 205 and abs(cr - cg) < 18 and abs(cg - cb) < 18:
                pts.add((x, y))

    best = None
    while pts:
        stack = [next(iter(pts))]
        comp = []
        while stack:
            q = stack.pop()
            if q in pts:
                pts.discard(q)
                comp.append(q)
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        n = (q[0] + dx, q[1] + dy)
                        if n in pts:
                            stack.append(n)
        xs = [q[0] for q in comp]
        ys = [q[1] for q in comp]
        w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        # An X is small, roughly square, and a solid little cluster of strokes.
        if 8 <= w <= 40 and 8 <= h <= 40 and 0.6 < w / h < 1.7 and len(comp) >= 20:
            if best is None or len(comp) > best[0]:
                best = (len(comp), ((min(xs) + max(xs)) // 2,
                                    (min(ys) + max(ys)) // 2))
    return best[1] if best else None


def dismiss_modal(verbose=True):
    """Close a dimmed-backdrop modal by its X. Returns True if one was closed."""
    img = _capture()
    if not backdrop_dimmed(img):
        return False
    box = modal_box(img)
    if box is None:
        if verbose:
            print("    Dimmed backdrop but no dialog box found")
        return False
    target = find_close_x(img, box)
    if target is None:
        if verbose:
            print(f"    Modal at {box} but no close X found — leaving it")
        return False
    if verbose:
        print(f"    Modal at {box}, clicking its X at {target}")
    pyautogui.click(*target)
    time.sleep(1.5)
    if backdrop_dimmed(_capture()):
        if verbose:
            print("    ⚠ backdrop still dimmed after clicking the X")
        return False
    if verbose:
        print("    Modal closed")
    return True


def dismiss(rounds=3, verbose=True):
    """Close every registered popup currently on screen.

    Returns the list of popup names actually dismissed. Each close is verified
    by re-checking the signature, so a stale coordinate reports a failure
    instead of silently doing nothing.
    """
    closed = []
    for _ in range(rounds):
        found = identify()
        if not found:
            break
        spec, score, target = found
        if verbose:
            print(f"    Known popup: {spec['name']} (match {score:.1f}), "
                  f"clicking close at {target}")
        pyautogui.click(*target)
        time.sleep(1.2)
        still = identify()
        if still and still[0]["name"] == spec["name"]:
            if verbose:
                print(f"    ⚠ {spec['name']} still on screen after clicking "
                      f"{target} — the close offset may be stale. Re-measure "
                      f"with: python3 popups.py --capture")
            break
        closed.append(spec["name"])
        if verbose:
            print(f"    Closed: {spec['name']}")
    return closed


def save_study_shot(tag="popup"):
    """Save a full screencapture for working out a new popup's signature."""
    return display.save_debug_shot(f"popup_study_{tag}")


if __name__ == "__main__":
    import sys
    if "--capture" in sys.argv:
        save_study_shot()
    elif "--dismiss" in sys.argv:
        print("Dismissed:", dismiss() or "nothing")
    else:
        found = identify()
        if found:
            spec, score, target = found
            print(f"Popup on screen: {spec['name']} "
                  f"(match {score:.1f} <= {spec['threshold']}), "
                  f"close target {target}")
        else:
            print("No registered popup detected.")
            print(f"Registry holds {len(KNOWN_POPUPS)}: "
                  + ", ".join(p["name"] for p in KNOWN_POPUPS))
