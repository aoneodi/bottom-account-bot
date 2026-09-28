"""Build and send the per-brand report for a completed run.

`send_email.send_success_report()` only knows which screenshots were taken, and
states "Screenshots have been inserted into Google Slides" unconditionally —
so a run where the Slides step failed would still report success. CLAUDE.md
requires the report to say, per brand, whether the screenshot was captured AND
whether it was inserted, and to surface failures explicitly so the user knows
what to redo by hand. That is what this does.

Status is read back from evidence rather than assumed:
  * screenshot — the file for today actually exists on disk
  * inserted   — the brand is absent from insert_to_slides.py's failure list
                 AND that step exited 0

Usage:
  python3 report_run.py --log logs/weekly_20260921.log --brands "A B C" \
      --shot-rc 0 --slides-rc 0 [--subject-prefix "[REHEARSAL] "] [--dry-run]
"""
import argparse
import os
import re
from datetime import datetime

from config import SCREENSHOT_DIR, DATE_FILTERS


def screenshot_present(akun, stamp):
    return all(
        os.path.exists(os.path.join(SCREENSHOT_DIR, f"{akun}_{f}_{stamp}.png"))
        for f in DATE_FILTERS
    )


def parse_log(path):
    """Return (slides_failures, skipped_by_bot, bad_metrics, blocked_by_modal)."""
    failures, skipped, bad_metrics, modal = {}, [], {}, set()
    if not path or not os.path.exists(path):
        return failures, skipped
    text = open(path, errors="replace").read()

    # insert_to_slides.py: "    - AKUN: reason" under "⚠ FAILED brands"
    tail = text.split("FAILED brands")[-1] if "FAILED brands" in text else ""
    for m in re.finditer(r"^\s+- (\S+): (.+)$", tail, re.M):
        failures[m.group(1)] = m.group(2).strip()
    # and the inline marker, in case the summary block is missing
    for m in re.finditer(r"✗ (\S+) FAILED", text):
        failures.setdefault(m.group(1), "API error after retries")

    # shopee_ads_screenshot.py: brands skipped because the shop was not found
    if "NOT FOUND (skipped" in text:
        blk = text.split("NOT FOUND (skipped")[-1]
        for m in re.finditer(r"^\s+- (\S+)\s*$", blk, re.M):
            skipped.append(m.group(1))

    # A screenshot can exist and still be worthless: if the metric cards were
    # not left on Pengeluaran + ROAS, the chart shows the wrong series. On
    # 2026-09-24 three brands were reported "done" on exactly that basis and the
    # wrong charts went into the decks. The bot already prints this; the report
    # just never read it.
    for m in re.finditer(r"METRICS NOT AS REQUESTED for (\S+?):\s*(.+?)\s+still wrong", text):
        bad_metrics[m.group(1)] = f"wrong metrics on the chart ({m.group(2)})"

    # A modal the handler could not close usually means the capture is of the
    # popup rather than the Performa section.
    for m in re.finditer(r"no close X found", text):
        pass
    cur = None
    for line in text.splitlines():
        b = re.match(r"^Processing: (\S+)", line)
        if b:
            cur = b.group(1)
        elif cur and ("no close X found" in line or "REFUSING to click" in line):
            modal.add(cur)
    return failures, skipped, bad_metrics, modal


def build(brands, log, shot_rc, slides_rc, stamp):
    failures, skipped, bad_metrics, modal = parse_log(log)
    rows, ok = [], 0
    for b in brands:
        shot = screenshot_present(b, stamp)
        if not shot:
            why = "shop not found on Pilih Toko" if b in skipped else "not captured"
            rows.append((b, "NO", "-", why))
            continue
        # The file existing is not the same as the capture being usable.
        if b in bad_metrics:
            rows.append((b, "BAD", "inserted" if slides_rc == 0 and b not in failures
                         else "NO", bad_metrics[b] + " — REDO, the deck has the wrong chart"))
            continue
        if b in modal:
            rows.append((b, "BAD", "inserted" if slides_rc == 0 and b not in failures
                         else "NO",
                         "a popup could not be closed — the image is probably of the popup"))
            continue
        if b in failures:
            rows.append((b, "yes", "NO", failures[b]))
        elif slides_rc != 0:
            rows.append((b, "yes", "?", "Slides step exited non-zero — verify by hand"))
        else:
            rows.append((b, "yes", "yes", ""))
            ok += 1

    width = max([len(b) for b in brands] + [5])
    lines = [f"{'BRAND'.ljust(width)}  SHOT  SLIDES  NOTE",
             f"{'-' * width}  ----  ------  ----"]
    for b, s, i, n in rows:
        lines.append(f"{b.ljust(width)}  {s:<4}  {i:<6}  {n}")

    bad = [r for r in rows if r[1] != "yes" or r[2] != "yes"]
    junk = [r for r in rows if r[1] == "BAD"]
    body = [
        "Hi team,",
        "",
        f"Bottom Account run for {stamp}.",
        f"Fully done: {ok}/{len(brands)} brands.",
        "",
        *lines,
        "",
    ]
    if junk:
        body += ["!! WRONG IMAGE ALREADY IN THE DECKS — redo these first:",
                 *[f"  - {b}: {n}" for b, s, i, n in junk], ""]
    if bad:
        body += ["NEEDS A MANUAL REDO:",
                 *[f"  - {b}: {n or 'see log'}" for b, s, i, n in bad], ""]
    else:
        body += ["Nothing needs a manual redo.", ""]
    body += [f"Exit codes: screenshots={shot_rc}, slides={slides_rc}",
             f"Log: {log or '(none)'}", "", "Bottom Account Bot"]

    subject = (f"[Bottom Account Bot] {ok}/{len(brands)} done"
               + (f" — {len(bad)} need a redo" if bad else ""))
    return subject, "\n".join(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    ap.add_argument("--brands", required=True)
    ap.add_argument("--shot-rc", type=int, default=0)
    ap.add_argument("--slides-rc", type=int, default=0)
    ap.add_argument("--subject-prefix", default="")
    ap.add_argument("--stamp", default=datetime.now().strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    brands = [b for b in a.brands.split() if b]
    subject, body = build(brands, a.log, a.shot_rc, a.slides_rc, a.stamp)
    subject = a.subject_prefix + subject

    if a.dry_run:
        print("--- DRY RUN, not sent ---")
        print("Subject:", subject)
        print(body)
        return
    from send_email import send_email
    send_email(subject, body)
    print(f"Report sent: {subject}")


if __name__ == "__main__":
    main()
