#!/bin/zsh
# Pembungkus app untuk run_weekly.sh. Dua alasan, keduanya soal lingkungan launchd —
# pola yang sama dengan "AHA Crawler Tick.app", yang sudah membuktikannya:
#
# 1. Izin. macOS memberikan Screen Recording / Accessibility kepada proses penanggung
#    jawab. Dibuktikan 2026-09-21: launchd memanggil /bin/zsh langsung -> preflight
#    berhasil menggerakkan Chrome lewat AppleScript tetapi `screencapture` gagal dengan
#    "could not create image from display". Seluruh bot bergantung pada screencapture,
#    jadi ini fatal. Dibungkus app, izinnya menempel pada bundle ini saja — bukan pada
#    SEMUA skrip shell di Mac ini.
#
# 2. PATH. launchd memberi PATH minimal, sehingga `python3` jatuh ke /usr/bin/python3
#    yang TIDAK punya pyautogui/PIL. Homebrew didahulukan.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
REPO="/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot"

# --probe: buktikan izin TANPA menjalankan run satu jam. Hasil ditulis ke berkas
# karena launchd tidak memberi stdout yang bisa dibaca dari luar.
if [ "${1:-}" = "--probe" ]; then
  OUT="$REPO/logs/probe.log"
  mkdir -p "$REPO/logs"
  {
    echo "waktu        : $(date '+%F %T')"
    echo "python3      : $(command -v python3)"

    # What the bot actually does: every capture is driven from python, which
    # holds the Screen Recording grant. A bare `screencapture` straight from
    # this shell does NOT work under launchd ("could not create image from
    # display") — that is expected and harmless, because nothing in the bot
    # calls it that way. Do not "fix" it by granting this bundle Screen
    # Recording; it is not needed and the bundle never appears in that list.
    echo "capture (py) : $(python3 -c "
import subprocess, os
from PIL import Image
t = os.path.join('$REPO', 'logs', '_probe_py.png')
if os.path.exists(t): os.remove(t)
subprocess.run(['screencapture', '-x', t], capture_output=True)
if os.path.exists(t):
    im = Image.open(t); print('OK', im.size); os.remove(t)
else:
    print('GAGAL - bot tidak akan bisa memotret layar')
" 2>&1 | tail -1)"

    echo "apple events : $(osascript -e 'tell application "System Events" to return (name of processes) contains "Google Chrome"' 2>&1)"

    # Accessibility: pyautogui posts CGEvents to move the pointer. Moving it to
    # where it already is proves the permission without disturbing anything.
    echo "accessibility: $(python3 -c "
import pyautogui
p = pyautogui.position()
pyautogui.moveTo(p.x, p.y)
q = pyautogui.position()
print('OK' if (q.x, q.y) == (p.x, p.y) else f'MERAGUKAN {p} -> {q}')
" 2>&1 | tail -1)"

    echo "--- preflight (jalur produksi sesungguhnya) ---"
    cd "$REPO" && python3 preflight.py 2>&1
    echo "preflight exit: $?   (0=siap 1=belum login 2=error)"
  } > "$OUT" 2>&1
  exit 0
fi

exec /bin/zsh "$REPO/run_weekly.sh"
