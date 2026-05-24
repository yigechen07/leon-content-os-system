#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/yige/Desktop/IP"
LABEL="com.leon.ip.watchdog"
SRC="$ROOT/00_System/launchd/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$ROOT/00_System/logs"
cp "$SRC" "$DST"

launchctl bootout "gui/$(id -u)" "$DST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$DST"
launchctl enable "gui/$(id -u)/$LABEL"

echo "Installed and loaded $DST"
