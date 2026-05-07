#!/usr/bin/env bash
# Removes all files installed by install.sh. Leaves config.ron and
# captured files alone unless --purge is passed.
set -euo pipefail

PURGE=0
if [[ "${1:-}" == "--purge" ]]; then PURGE=1; fi

BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/cosmic-capture"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cosmic-capture"
PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/cosmic-capture.pid"

rm -f "$BIN_DIR/cosmic-capture"
rm -rf "$SHARE_DIR"
rm -f "$APPS_DIR/cosmic-capture.desktop"
rm -f "$ICONS_DIR/cosmic-capture.svg"
update-desktop-database "$APPS_DIR" 2>/dev/null || true
gtk-update-icon-cache -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
rm -f "$PID_FILE"

if (( PURGE )); then
    rm -rf "$CONFIG_DIR"
    echo "Config and pid file removed."
else
    echo "Config preserved at $CONFIG_DIR"
    echo "(Pass --purge to also remove it.)"
fi

echo "Cosmic Capture uninstalled."
echo "Note: this does not remove apt packages, the gpu-screen-recorder"
echo "flatpak, your dock favorite, or your COSMIC shortcut. Edit those"
echo "yourself if needed."
