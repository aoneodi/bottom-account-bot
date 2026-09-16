SELLER_CENTER_URL = "https://seller.shopee.co.id"
SLIDES_ID = "1Ott0JcNme2979Obe4VpJNQey7Pyr6mP5YNGeK2XiFC4"
MEETING_SLIDES_IDS = [
    "12BCe2jvkoG1z01il6bBQRHkW3Z2aOSMUAIKG8JzqFuM",
    "1f2QVMCagabXk6RidXLIYhpI6uBCVBougOKs7RPEotCE",
]
MEETING_SLIDES_ID = MEETING_SLIDES_IDS[0]  # back-compat for any old refs

SCREENSHOT_DIR = "screenshots"

# Email notification
EMAIL_SENDER = "bot@ahacommerce.net"  # impersonated via service-account domain-wide delegation
EMAIL_SENDER_NAME = "AHAbot™"  # display name shown on the From line
EMAIL_RECIPIENTS = ["tfbi@ahacommerce.net", "claudia.ong@ahacommerce.net"]

# Timing configs (seconds) - adjust if Shopee is slow
PAGE_LOAD_WAIT = 3
CLICK_DELAY = 1
SCROLL_DELAY = 1
POPUP_WAIT = 2
