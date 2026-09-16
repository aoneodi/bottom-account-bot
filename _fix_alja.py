"""One-off: re-capture ALJA-M with a FORCED deselect of 'Penjualan dari Iklan'.

ALJA-M's metric-card border detection deterministically misses the orange top
border of 'Penjualan dari Iklan' (its calibrated position puts the border just
outside the sampling strip), so the auto-deselect leaves it on → 3 metrics in
the chart instead of the required Biaya Iklan + ROAS.

Clicking the card is reliable (only the thin-border detection is fragile), and
the card is known to be ON (sticky state, confirmed in the latest screenshot),
so here we just click it once to turn it off, leave Biaya + ROAS untouched, and
screenshot both date ranges.
"""
import time
import pyautogui
import shopee_ads_screenshot as s

AKUN = "ALJA-M"


def main():
    username = s.BRANDS[AKUN]
    print("Starting in 10 seconds — switch to Shopee 'Pilih Toko' now!")
    for i in range(10, 0, -1):
        print(f"  ...{i}")
        time.sleep(1)

    print("Searching for shop...")
    if not s.search_and_verify(AKUN, username):
        print(f"{AKUN} not found — aborting.")
        return

    print("Clicking Detail + navigating to Iklan Shopee...")
    s.click_first_detail()
    s.click_iklan_shopee(AKUN)
    s.close_popup()
    s.scroll_to_performa()

    print("Forcing 'Semua Iklan Produk' tab...")
    pyautogui.click(*s.SEMUA_IKLAN_PRODUK_TAB)
    time.sleep(2)

    y_offset = s.detect_y_offset()

    # Force-deselect 'Penjualan dari Iklan' (known ON). Leave Biaya Iklan + ROAS.
    px, py = s.METRIC_CARDS["Penjualan dari Iklan"]
    print(f"Clicking 'Penjualan dari Iklan' at ({px}, {py + y_offset}) to deselect...")
    pyautogui.click(px, py + y_offset)
    time.sleep(1.5)

    for filter_name in s.DATE_FILTERS:
        print(f"Selecting '{filter_name}' + screenshot...")
        s.select_date_filter(filter_name, y_offset=y_offset)
        s.take_screenshot(AKUN, filter_name, y_offset=y_offset)

    s.go_back_to_pilih_toko()
    print("DONE!")


if __name__ == "__main__":
    main()
