"""Check, before a run, that this python still holds every macOS permission the bots need.

Why this exists (2026-11-05): a Homebrew patch upgrade of python@3.14 (3.14.4 -> 3.14.10)
moved the interpreter to a new Cellar path. macOS grants Screen Recording, Accessibility
and Automation per binary PATH, so every grant silently stayed on the old path:

  * Automation (python -> Chrome): osascript hung on an unanswered consent prompt, then
    was recorded as denied. Shopee's preflight said "Chrome is not running" on all 7 ticks.
  * Accessibility / PostEvent: pyautogui clicks and keystrokes are DROPPED without any
    error. The bot "ran" for 10 minutes, logging "navigation did not stick" for every brand.

Neither failure named its cause, and nobody was told until the team noticed an empty deck.
This check names the missing permission and emails the fix, once per day.

Must be run by the SAME python the bots use, launched the same way (launchd via the .app
wrapper): macOS checks the responsible process, so a check from Terminal proves nothing.

Exit 0 = all granted, 1 = something missing (printed, and emailed with --alert).
"""
import argparse
import ctypes
import os
import subprocess
import sys

FIX = {
    "Screen Recording": "Privacy & Security -> Screen Recording",
    "Accessibility (mouse/keyboard)": "Privacy & Security -> Accessibility",
    "Automation -> Google Chrome": "Privacy & Security -> Automation -> python3.14 -> Google Chrome",
}


def _quartz_checks():
    missing = []
    try:
        AS = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        CG = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        for f in (AS.AXIsProcessTrusted, CG.CGPreflightPostEventAccess,
                  CG.CGPreflightScreenCaptureAccess):
            f.restype = ctypes.c_bool
        if not CG.CGPreflightScreenCaptureAccess():
            missing.append("Screen Recording")
        if not (AS.AXIsProcessTrusted() and CG.CGPreflightPostEventAccess()):
            missing.append("Accessibility (mouse/keyboard)")
    except Exception as e:                      # never block a run on the checker itself
        print(f"  perms: quartz check skipped ({e})")
    return missing


def _automation_check():
    """-1743 is errAEEventNotPermitted. A timeout means a consent prompt is waiting
    for someone to click it — just as fatal for an unattended run."""
    try:
        r = subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to count windows'],
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return ["Automation -> Google Chrome"]
    if r.returncode != 0 and ("-1743" in r.stderr or "not allowed" in r.stderr.lower()):
        return ["Automation -> Google Chrome"]
    if r.returncode != 0:
        print(f"  perms: Chrome automation check inconclusive: {r.stderr.strip()[:120]}")
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", metavar="MARKER",
                    help="email the fix if anything is missing, unless MARKER exists; then create it")
    ap.add_argument("--bot", default="Bottom Account")
    args = ap.parse_args()

    missing = _quartz_checks() + _automation_check()
    exe = os.path.realpath(sys.executable)
    if not missing:
        print(f"  perms: OK ({exe})")
        return 0

    print(f"  perms: MISSING {', '.join(missing)} for {exe}")
    if args.alert and not os.path.exists(args.alert):
        body = "\n".join([
            "Hi team,",
            "",
            f"The {args.bot} bot cannot run: macOS has not given python the permission(s) below.",
            "This usually happens after a Python update (macOS ties each permission to the exact",
            "program file, and an update moves it). The bot will retry every 15 minutes, so",
            "fixing it now still saves today's run.",
            "",
            *[f"  - {m}:  System Settings -> {FIX[m]}" for m in missing],
            "",
            "Turn the switch ON for python3.14. If there are two python3.14 entries, turn on both.",
            "If python3.14 is not in the Accessibility / Screen Recording list, click + , press",
            "Cmd+Shift+G and paste:",
            f"  {exe}",
            "",
            "Bottom Account Bot",
        ])
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from send_email import send_email
            send_email(f"[{args.bot}] ACTION NEEDED — macOS permission missing, run blocked", body)
            open(args.alert, "w").close()
        except Exception as e:
            print(f"  perms: WARNING could not send the alert: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
