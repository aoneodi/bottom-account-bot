"""Archive the run's screenshots to Google Cloud Storage.

Why GCS when insert_to_slides.py already puts images on Drive: those Drive
copies exist only to give Slides a URL to fetch, they are flat and unstructured,
and nothing else can navigate them. This archive is for **other systems** to
read — one predictable path per brand per run date.

Layout:  gs://<bucket>/bottom-account/<YYYY-MM-DD>/<AKUN>_<filter>.png

The bucket is private (see setup_gcs.sh). These images carry client ROAS, ad
spend and revenue, so nothing here makes an object public and the bot holds
only `objectCreator` — it can write, not read back or delete. A separate
read-only service account is what other systems authenticate with.

Uploading runs as its own step AFTER the captures, never inside take_screenshot:
a storage outage must not cost a screenshot that was captured correctly.

Usage:
  python3 gcs_upload.py                      # today's screenshots
  python3 gcs_upload.py --stamp 20260924     # a specific run date
  python3 gcs_upload.py --include-debug      # also the _dbg_* failure frames
  python3 gcs_upload.py --dry-run
"""
import argparse
import glob
import os
import sys
from datetime import datetime

from config import SCREENSHOT_DIR

try:
    from config import GCS_BUCKET
except ImportError:
    GCS_BUCKET = ""

PREFIX = "bottom-account"
SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "service_account.json")


def _client():
    from google.cloud import storage
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )
    return storage.Client(credentials=creds, project=creds.project_id)


def collect(stamp, include_debug=False):
    files = sorted(glob.glob(os.path.join(SCREENSHOT_DIR, f"*_{stamp}.png")))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    if include_debug:
        files += sorted(glob.glob(os.path.join(SCREENSHOT_DIR, f"_dbg_*{stamp}*.png")))
    return files


def object_path(local, stamp):
    day = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    name = os.path.basename(local).replace(f"_{stamp}", "")
    return f"{PREFIX}/{day}/{name}"


def upload_one(local_path, stamp=None, bucket_name=None):
    """Upload one screenshot and return its gs:// path."""
    from datetime import datetime as _dt
    stamp = stamp or _dt.now().strftime("%Y%m%d")
    bucket_name = bucket_name or GCS_BUCKET
    dest = object_path(local_path, stamp)
    _client().bucket(bucket_name).blob(dest).upload_from_filename(
        local_path, content_type="image/png")
    return f"gs://{bucket_name}/{dest}"


def signed_url(local_path, stamp=None, bucket_name=None, minutes=30):
    """A short-lived HTTPS URL Google Slides can fetch the image from.

    The bucket stays private. Slides needs to pull the image over plain HTTPS at
    insert time, and it keeps its own copy afterwards, so a URL that expires in
    half an hour is enough. This is strictly tighter than the Drive path it
    replaces, which granted `anyone/reader` permanently and never revoked it —
    460+ images were still world-readable by link as of 2026-09-28.

    Signing happens locally with the service-account key, but a V4 signed URL is
    only honoured as far as the signer's own IAM allows, which is why the bot
    needs objectViewer on the bucket as well as objectCreator.
    """
    from datetime import timedelta
    stamp = stamp or datetime.now().strftime("%Y%m%d")
    bucket_name = bucket_name or GCS_BUCKET
    blob = _client().bucket(bucket_name).blob(object_path(local_path, stamp))
    return blob.generate_signed_url(version="v4",
                                    expiration=timedelta(minutes=minutes),
                                    method="GET")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", default=datetime.now().strftime("%Y%m%d"))
    ap.add_argument("--bucket", default=GCS_BUCKET)
    ap.add_argument("--include-debug", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.bucket:
        print("GCS_BUCKET is not set in config.py — skipping upload.")
        return 0

    files = collect(a.stamp, a.include_debug)
    if not files:
        print(f"No screenshots for {a.stamp} — nothing to upload.")
        return 0

    if a.dry_run:
        for f in files:
            print(f"  would upload {f} -> gs://{a.bucket}/{object_path(f, a.stamp)}")
        return 0

    client = _client()
    bucket = client.bucket(a.bucket)
    ok = 0
    for f in files:
        dest = object_path(f, a.stamp)
        try:
            bucket.blob(dest).upload_from_filename(f, content_type="image/png")
            print(f"  uploaded gs://{a.bucket}/{dest}")
            ok += 1
        except Exception as e:                      # keep going; one bad object
            print(f"  ⚠ failed {f}: {type(e).__name__}: {e}")
    print(f"Uploaded {ok}/{len(files)} to gs://{a.bucket}/{PREFIX}/")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
