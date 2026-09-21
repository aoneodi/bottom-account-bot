#!/bin/zsh
# Bottom Account — Claude-driven weekly run (WITH visual verification).
#
# Double-click this. A Terminal opens, Claude Code launches with the
# /bottom-run command already typed in — just press ENTER to start.
#
# Claude will: fetch this week's brands, screenshot Shopee ads, SHOW you the
# screenshots to verify, then (after your OK) insert into Slides and email the
# detailed report.
#
# PRECONDITION: log in to Shopee Seller Centre and be on the "Pilih Toko" page
# BEFORE you press Enter. Don't touch the mouse/keyboard once the bot's 10s
# countdown starts; slam the mouse to a screen corner to abort.

cd "/Users/ahabot/Documents/Claudia/bottom-account-shopee-bot" || {
  echo "Project dir not found."; read "?Press Enter to close..."; exit 1;
}

exec /Users/ahabot/.local/bin/claude "/bottom-run"
