"""Manual screenshot capture for one brand.
You set up the Iklan Shopee page (correct metric cards selected, correct date filter),
then click OK in each dialog to trigger a screenshot."""
import os
import subprocess
import sys
from datetime import datetime
from PIL import Image

from config import SCREENSHOT_DIR, DATE_FILTERS
from shopee_ads_screenshot import CROP_TOP_LEFT, CROP_BOTTOM_RIGHT

AKUN = sys.argv[1].upper() if len(sys.argv) > 1 else "ALUN-M"
timestamp = datetime.now().strftime("%Y%m%d")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def capture(filter_name):
    subprocess.run([
        "osascript", "-e",
        f'display dialog "Set up the page for {AKUN} {filter_name} (correct metrics + correct date filter), then click OK to capture." with title "Manual Capture" buttons {{"OK"}} default button "OK"'
    ])
    filepath = os.path.join(SCREENSHOT_DIR, f"{AKUN}_{filter_name}_{timestamp}.png")
    tmp_path = os.path.join(SCREENSHOT_DIR, "_tmp_full.png")
    subprocess.run(["screencapture", "-x", tmp_path])
    img = Image.open(tmp_path)
    x1 = CROP_TOP_LEFT[0] * 2
    y1 = CROP_TOP_LEFT[1] * 2
    x2 = CROP_BOTTOM_RIGHT[0] * 2
    y2 = CROP_BOTTOM_RIGHT[1] * 2
    img.crop((x1, y1, x2, y2)).save(filepath)
    os.remove(tmp_path)
    print(f"Saved: {filepath}")


for _filter in DATE_FILTERS:  # just "1bulan" since 2026-09-16
    capture(_filter)
print("Done.")
