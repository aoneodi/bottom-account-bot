"""Sync brands.csv from the "Monitored Stores" tab (source of truth since 2026-08-06,
replacing the deleted master-sheet BRAND tab).

Sheet: 1s4MAeV0TMoIA8i0t5xHlxsj01j5uDlNmOliIt7biknY, tab "Monitored Stores",
cols A-C (A = akun, B = Nama/Username SHO, C = kode partner). Rows 1-2 are the
section title + header.

Behavior: akun present in the sheet but missing from brands.csv is APPENDED;
akun present in both with a DIFFERENT username is only REPORTED (never
overwritten — csv values have been verified against live captures, the sheet
has had stale usernames, e.g. TH.WONE-M). Run with --dry-run to preview.
"""
import csv
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

MAPPING_SHEET_ID = "1s4MAeV0TMoIA8i0t5xHlxsj01j5uDlNmOliIt7biknY"
MAPPING_RANGE = "Monitored Stores!A3:B500"
BRANDS_CSV = "brands.csv"


def fetch_sheet_mapping():
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    svc = build("sheets", "v4", credentials=creds)
    vals = svc.spreadsheets().values().get(
        spreadsheetId=MAPPING_SHEET_ID, range=MAPPING_RANGE
    ).execute().get("values", [])
    mapping = {}
    for row in vals:
        if not row or not row[0].strip():
            continue
        akun = row[0].strip().upper()
        username = row[1].strip() if len(row) > 1 else ""
        if username and username != "-" and akun != "AKUN":
            mapping[akun] = username
    return mapping


def main():
    dry_run = "--dry-run" in sys.argv
    sheet_map = fetch_sheet_mapping()
    with open(BRANDS_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    csv_map = {r["akun"].strip().upper(): r["shopee_username"].strip() for r in rows}

    added, conflicts = [], []
    for akun, username in sorted(sheet_map.items()):
        if akun not in csv_map:
            rows.append({"akun": akun, "shopee_username": username})
            added.append(f"{akun} -> {username}")
        elif csv_map[akun] != username:
            conflicts.append(f"{akun}: csv={csv_map[akun]!r} sheet={username!r} (csv kept)")

    csv_only = sorted(set(csv_map) - set(sheet_map))

    print(f"Sheet entries: {len(sheet_map)} | csv entries before: {len(csv_map)}")
    print(f"\nAdded ({len(added)}):")
    print("\n".join(f"  {a}" for a in added) or "  (none)")
    print(f"\nUsername conflicts, NOT overwritten ({len(conflicts)}):")
    print("\n".join(f"  {c}" for c in conflicts) or "  (none)")
    print(f"\nIn csv but not in sheet ({len(csv_only)}): {', '.join(csv_only) or '(none)'}")

    if dry_run:
        print("\nDRY RUN — brands.csv not written.")
        return
    if added:
        with open(BRANDS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["akun", "shopee_username"])
            writer.writeheader()
            writer.writerows(
                {"akun": r["akun"].strip(), "shopee_username": r["shopee_username"].strip()}
                for r in rows
            )
        print(f"\nbrands.csv updated ({len(csv_map) + len(added)} entries).")
    else:
        print("\nNothing to add — brands.csv untouched.")


if __name__ == "__main__":
    main()
