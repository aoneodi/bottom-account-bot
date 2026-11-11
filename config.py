SELLER_CENTER_URL = "https://seller.shopee.co.id"
SLIDES_ID = "1Ott0JcNme2979Obe4VpJNQey7Pyr6mP5YNGeK2XiFC4"
MEETING_SLIDES_IDS = [
    "12BCe2jvkoG1z01il6bBQRHkW3Z2aOSMUAIKG8JzqFuM",
    "1f2QVMCagabXk6RidXLIYhpI6uBCVBougOKs7RPEotCE",
]
MEETING_SLIDES_ID = MEETING_SLIDES_IDS[0]  # back-compat for any old refs

SCREENSHOT_DIR = "screenshots"

# Date ranges captured (and inserted into Slides) per brand, in order.
# Since 2026-09-16 the Bottom Account meeting only needs "1 bulan terakhir" —
# 3 bulan was dropped at the user's request. The 3bulan click coords
# (FILTER_3BULAN) and slide label are still in place, so adding "3bulan" back
# to this list re-enables it end-to-end.
DATE_FILTERS = ["1bulan"]

# Email notification
EMAIL_SENDER = "bot@ahacommerce.net"  # impersonated via service-account domain-wide delegation
EMAIL_SENDER_NAME = "AHAbot™"  # display name shown on the From line
EMAIL_RECIPIENTS = ["tfbi@ahacommerce.net", "claudia.ong@ahacommerce.net", "fast@ahacommerce.net"]

# Timing configs (seconds) - adjust if Shopee is slow
PAGE_LOAD_WAIT = 3
CLICK_DELAY = 1
SCROLL_DELAY = 1
POPUP_WAIT = 2

# Google Cloud Storage archive for the run's screenshots (see gcs_upload.py).
# Empty = upload step is skipped. Set this after running setup_gcs.sh.
# The bucket is private; other systems read it with their own service account.
GCS_BUCKET = ""

# Shared Drive yang memiliki arsip screenshot di Drive (lihat insert_to_slides.py).
# Kosong = kembali ke My Drive pribadi pemilik token OAuth.
DRIVE_SHARED_DRIVE_ID = "0AAJlr-VJ8_EzUk9PVA"   # AHA Bottom Account

# Prefiks marketplace pada nama berkas screenshot: SHO_<AKUN>_<filter>_<tanggal>.png
# Ada tiktok_ads_screenshot.py di repo ini dan sheet akun memisahkan SHO/LAZ/TOK/TIK,
# jadi arsipnya harus jelas dari marketplace mana tiap gambar berasal.
MARKETPLACE_PREFIX = "SHO"
