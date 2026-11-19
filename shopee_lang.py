"""Switch the Seller Centre UI language — English for Thai brands, Indonesian otherwise.

Asked for 2026-11-11: the Thai brands' screenshots should read in English. Shopee's
language is a setting of the whole ahacommerce:biteam account, NOT per country —
verified that day: switching to English on seller.shopee.co.th turned
seller.shopee.co.id English too. So the bot switches to English right before a TH.*
brand and back to Indonesian before the next Indonesian brand, and restores
Indonesian at the end of every run (run_weekly also starts with Indonesian brands,
which restores it if a previous run died while English).

The switch lives in the account menu (top-right "<shop> / ahacommerce:biteam ⌄"):
  menu row "<current language> >"  ->  submenu: English, Tiếng Việt, ..., Bahasa Indonesia
The menu only opens on a REAL click (a JS click did nothing), so the clicks go through
pyautogui; the targets are found by their text, not by fixed coordinates.
"""
import json
import subprocess
import time

import pyautogui

# OFF until the switch is proven: on 2026-11-11 the submenu did not open from the bot,
# and a leftover test job then re-ran the bot all night. Turn on only after a clean test.
ENABLED = False

LABELS = {"en": "English", "id": "Bahasa Indonesia (Indonesian)"}
ACCOUNT = "ahacommerce:biteam"


def _js(code):
    r = subprocess.run(["osascript", "-e",
                        'tell application "Google Chrome" to execute active tab of window 1 '
                        f'javascript {json.dumps(code)}'],
                       capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def current():
    """'en' / 'id' / '' from the sidebar wording."""
    t = _js("(document.body&&document.body.innerText||'').slice(0,3000)")
    if "My Orders" in t or "Shopee Ads" in t:
        return "en"
    if "Pesanan Saya" in t or "Iklan Shopee" in t:
        return "id"
    return ""


# Screen point of an element's centre: window origin + browser chrome + viewport offset.
_POINT_JS = r"""(function(match){
  var hit=null;
  document.querySelectorAll('*').forEach(function(e){
    if(e.children.length) return; var r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) return;
    if(match(e,r)) hit=e;
  });
  if(!hit) return '';
  var r=hit.getBoundingClientRect();
  return JSON.stringify({x:Math.round(screenX+r.left+r.width/2),
                         y:Math.round(screenY+(outerHeight-innerHeight)+r.top+r.height/2)});
})(%s)"""


def _point(match_js):
    out = _js(_POINT_JS % match_js)
    return json.loads(out) if out else None


def switch(lang, log=print):
    """Switch the account language to `lang` ('en'/'id'). True when it took."""
    if current() == lang:
        return True
    label = LABELS[lang]
    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'])
    time.sleep(0.8)
    acct = _point("function(e){return (e.innerText||'').trim()===%s}" % json.dumps(ACCOUNT))
    if not acct:
        log("    ⚠ language: account menu not found")
        return False
    pyautogui.click(acct["x"], acct["y"])
    time.sleep(1.5)
    # The menu row that shows the CURRENT language; hovering it opens the submenu.
    row = _point("function(e,r){var t=(e.innerText||'').trim();"
                 "return r.top<700&&r.left>1200&&(t==='English'||t==='Bahasa Indonesia (Indonesian)')"
                 "}")
    if not row:
        log("    ⚠ language: language row not found in the account menu")
        pyautogui.press("escape")
        return False
    pyautogui.moveTo(row["x"], row["y"], duration=0.3)
    time.sleep(1.5)
    # The submenu is the list that also holds "Tiếng Việt"; take the label from there.
    target = _js(r"""(function(label){
      var vi=null; document.querySelectorAll('*').forEach(function(e){
        if(!e.children.length&&(e.innerText||'').trim()==='Tiếng Việt (Vietnamese)'&&e.getBoundingClientRect().width>0) vi=e;});
      if(!vi) return '';
      for(var box=vi.parentElement; box && box!==document.body; box=box.parentElement){
        var hit=null; box.querySelectorAll('*').forEach(function(e){
          if(!e.children.length&&(e.innerText||'').trim()===label&&e.getBoundingClientRect().width>0) hit=e;});
        if(hit){ var r=hit.getBoundingClientRect();
          return JSON.stringify({x:Math.round(screenX+r.left+r.width/2),
                                 y:Math.round(screenY+(outerHeight-innerHeight)+r.top+r.height/2)}); }
      }
      return '';
    })(%s)""" % json.dumps(label))
    if not target:
        log("    ⚠ language: submenu did not open")
        pyautogui.press("escape")
        return False
    t = json.loads(target)
    # Slide into the submenu at the row's height first, so the pointer never leaves
    # the menu on the way (that would close it).
    pyautogui.moveTo(t["x"], row["y"], duration=0.25)
    pyautogui.moveTo(t["x"], t["y"], duration=0.25)
    pyautogui.click()
    for _ in range(10):
        time.sleep(2)
        if current() == lang:
            log(f"    language → {label}")
            time.sleep(3)
            return True
    log(f"    ⚠ language: still not {label} after switching")
    return False


def restore_indonesian(log=print):
    """End of run: leave the shared account in Indonesian, as the team uses it."""
    if current() == "id":
        return True
    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to set URL of active tab '
                    'of window 1 to "https://seller.shopee.co.id/portal/marketing/pas/index"'])
    time.sleep(15)
    return switch("id", log)
