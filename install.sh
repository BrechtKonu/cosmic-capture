#!/usr/bin/env bash
# Cosmic Capture installer.
# Copies files into ~/.local/{bin,share,share/applications}, drops a
# default config.ron, and prints next steps. Idempotent.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/cosmic-capture"
APPS_DIR="$HOME/.local/share/applications"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cosmic-capture"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m!!\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m✓\033[0m   %s\n' "$*"; }

info "Installing Cosmic Capture from $REPO_DIR"

# --- runtime deps ---------------------------------------------------------
APT_NEEDED=()
for pkg in slurp cosmic-screenshot python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
           libnotify-bin rclone wl-clipboard python3-pil; do
    case "$pkg" in
        slurp)               command -v slurp            >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
        cosmic-screenshot)   command -v cosmic-screenshot >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
        libnotify-bin)       command -v notify-send      >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
        rclone)              command -v rclone           >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
        wl-clipboard)        command -v wl-copy          >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
        python3-pil)         python3 -c "import PIL" 2>/dev/null         || APT_NEEDED+=("$pkg") ;;
        python3-gi|gir1.2-gtk-4.0|gir1.2-adw-1)
            dpkg -s "$pkg" >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
    esac
done

if [[ ${#APT_NEEDED[@]} -gt 0 ]]; then
    warn "Missing apt packages: ${APT_NEEDED[*]}"
    read -rp "Install them now with sudo apt? [Y/n] " ans
    if [[ -z "$ans" || "$ans" =~ ^[Yy] ]]; then
        sudo apt update
        sudo apt install -y "${APT_NEEDED[@]}"
    else
        warn "Skipping apt install — you'll need to install those manually."
    fi
else
    ok "All apt dependencies present"
fi

# --- gpu-screen-recorder (flatpak, system-wide) ---------------------------
if ! flatpak list --system --app 2>/dev/null | grep -q com.dec05eba.gpu_screen_recorder; then
    warn "gpu-screen-recorder flatpak not installed system-wide."
    warn "  (User installs are broken: the app hardcodes /var/lib/flatpak paths.)"
    read -rp "Install it now? [Y/n] " ans
    if [[ -z "$ans" || "$ans" =~ ^[Yy] ]]; then
        sudo flatpak remote-add --if-not-exists flathub \
            https://dl.flathub.org/repo/flathub.flatpakrepo
        flatpak install --system -y flathub com.dec05eba.gpu_screen_recorder
    fi
else
    ok "gpu-screen-recorder flatpak present"
fi

# --- copy files -----------------------------------------------------------
mkdir -p "$BIN_DIR" "$SHARE_DIR" "$APPS_DIR" "$CONFIG_DIR"
install -m 755 "$REPO_DIR/bin/cosmic-capture"           "$BIN_DIR/cosmic-capture"
install -m 755 "$REPO_DIR/share/overlay.py"             "$SHARE_DIR/overlay.py"
install -m 755 "$REPO_DIR/share/screenshot.py"          "$SHARE_DIR/screenshot.py"
install -m 755 "$REPO_DIR/share/record.py"              "$SHARE_DIR/record.py"
install -m 755 "$REPO_DIR/share/recorder_hud.py"        "$SHARE_DIR/recorder_hud.py"
install -m 755 "$REPO_DIR/share/sync_and_share.py"      "$SHARE_DIR/sync_and_share.py"
# Substitute the user's absolute binary path into Exec= so cosmic-comp's
# Spawn context (which may not have ~/.local/bin on PATH) still finds us.
sed "s|^Exec=.*|Exec=$BIN_DIR/cosmic-capture|" \
    "$REPO_DIR/applications/cosmic-capture.desktop" \
    > "$APPS_DIR/cosmic-capture.desktop"
chmod 644 "$APPS_DIR/cosmic-capture.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true
ok "Files installed"

# --- optional: satty (annotation) ----------------------------------------
if ! command -v satty >/dev/null 2>&1; then
    info "Optional: install 'satty' for screenshot annotation."
    info "  cargo install satty   (or grab a release from"
    info "  https://github.com/gabm/satty/releases)"
else
    ok "satty present (annotation enabled)"
fi

# --- config ---------------------------------------------------------------
if [[ ! -f "$CONFIG_DIR/config.ron" ]]; then
    cp "$REPO_DIR/config/config.ron.example" "$CONFIG_DIR/config.ron"
    sed -i "s|/home/YOU|$HOME|g" "$CONFIG_DIR/config.ron"
    ok "Default config written to $CONFIG_DIR/config.ron"
else
    ok "Existing config.ron kept — review it against config.ron.example if upgrading"
fi

# --- capture folders ------------------------------------------------------
mkdir -p "$HOME/Pictures/Screenshots" "$HOME/Videos/Screenrecordings"

# --- next steps -----------------------------------------------------------
cat <<EOF

Next steps:

1. Pin to dock (optional):
   Edit ~/.config/cosmic/com.system76.CosmicAppList/v1/favorites
   and add the line:   "cosmic-capture",
   Then: pkill cosmic-panel   (it auto-respawns)

2. Keyboard shortcut (optional):
   See $REPO_DIR/config/shortcuts.ron and merge into
   ~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom

3. Google Drive sync (optional):
   rclone config         # create a remote, name it per config.ron (default "gdrive")
   Then edit $CONFIG_DIR/config.ron and set drive.remote / drive.base_folder.
   Leave drive.base_folder = "" to disable upload.

4. Test:
   gtk-launch cosmic-capture

EOF

ok "Install complete."
