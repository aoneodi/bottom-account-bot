"""Logical-vs-physical screen coordinates.

The bot mixes two coordinate systems: pyautogui clicks in *logical* points,
while `screencapture` writes *physical* pixels. On the MacBook's Retina panel
the two differ by exactly 2x, and that factor was hardcoded as `* 2` in every
pixel read and every crop in the bot.

Moving to a 1x external display (Mi Monitor, 1920x1080) broke all of them at
once: pixel reads ran past the right/bottom edge of the capture (IndexError on
the row-2 cards, e.g. ROAS at logical x=1446 -> 2892 in a 1920-wide image), and
the screenshot crop fell entirely outside the frame — which PIL fills with black
rather than raising, so the bot would have reported success and pushed black
images into both meeting decks.

`scale()` measures the real ratio once from an actual screencapture, so the bot
follows whatever display it is running on instead of assuming Retina.

Note: `screencapture -x <one file>` and `pyautogui.size()` both refer to the
main display, so the two stay consistent on a multi-monitor setup. If a future
macOS merges several displays into one capture, the width/height ratios stop
agreeing and `_measure` warns.
"""
import os
import subprocess
import sys
import tempfile

import pyautogui
from PIL import Image

_scale = None


def scale():
    """Physical pixels per logical point on the main display.

    Measured lazily on first use (one screencapture) and cached for the run.
    """
    global _scale
    if _scale is None:
        _scale = _measure()
    return _scale


def _measure():
    fd, path = tempfile.mkstemp(prefix="_scale_probe_", suffix=".png")
    os.close(fd)
    try:
        subprocess.run(["screencapture", "-x", path], check=True)
        with Image.open(path) as img:
            px_w, px_h = img.size
    except (subprocess.CalledProcessError, OSError) as exc:
        raise RuntimeError(
            "Could not screencapture to measure the display scale. Check that the "
            "terminal has Screen Recording permission (System Settings -> Privacy "
            "& Security -> Screen Recording)."
        ) from exc
    finally:
        if os.path.exists(path):
            os.remove(path)

    logical_w, logical_h = pyautogui.size()
    if not logical_w or not logical_h:
        raise RuntimeError(
            f"pyautogui reported an unusable screen size: {logical_w}x{logical_h}"
        )

    sx = px_w / logical_w
    sy = px_h / logical_h
    if abs(sx - sy) > 0.01:
        print(
            f"[display] WARNING: non-uniform scale {sx:.3f} x {sy:.3f} "
            f"(captured {px_w}x{px_h}, logical {logical_w}x{logical_h}). "
            f"Using {sx:.3f} — if several monitors are attached, run the bot with "
            f"only one.",
            file=sys.stderr,
        )
    print(
        f"[display] {logical_w}x{logical_h} logical, {px_w}x{px_h} captured "
        f"-> scale {sx:g}x"
    )
    return sx


def save_debug_shot(tag, out_dir=None):
    """Save a full screencapture so a failure can be diagnosed after the fact.

    The bot runs unattended for ~an hour on Thursday mornings; when something
    goes wrong (an unrecognised popup, a layout shift, a page that never
    loaded) the screen is long gone by the time anyone looks. One frame is
    usually enough to work out what happened and, for a popup, to register it
    in popups.py — so anomalies save one instead of only printing a message.
    """
    import re
    from datetime import datetime
    if out_dir is None:
        from config import SCREENSHOT_DIR
        out_dir = SCREENSHOT_DIR
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(tag))
    path = os.path.join(
        out_dir, f"_dbg_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    subprocess.run(["screencapture", "-x", path])
    print(f"    [debug] saved {path}")
    return path


def px(value):
    """Logical points -> physical pixels, for indexing into a screencapture."""
    return int(round(value * scale()))


def to_logical(value):
    """Physical pixels -> logical points, for turning scan results into coords."""
    return int(round(value / scale()))


def sample(img, lx, ly):
    """RGB at a LOGICAL coordinate, or None if it falls outside the capture.

    Returning None rather than raising lets the pixel-scanning detectors skip
    out-of-frame samples and still reach a verdict, instead of an IndexError
    killing a whole run when coords are stale for the current display.
    """
    x, y = px(lx), px(ly)
    if not (0 <= x < img.width and 0 <= y < img.height):
        return None
    return img.getpixel((x, y))[:3]


def crop_logical(img, left, top, right, bottom):
    """Crop by LOGICAL coords, clamped to the image.

    Returns (cropped_image, clamped) — `clamped` is True when the requested box
    reached outside the capture, which means the coords no longer match this
    display. PIL would silently pad such a crop with black, so callers must
    surface it rather than saving the result as if it were good.
    """
    want = (px(left), px(top), px(right), px(bottom))
    safe = (
        max(0, want[0]),
        max(0, want[1]),
        min(img.width, want[2]),
        min(img.height, want[3]),
    )
    return img.crop(safe), safe != want
