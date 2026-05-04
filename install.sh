#!/usr/bin/env bash
# Cosmic Capture installer.
# Detects the host distro and prints package install commands for the
# runtime dependencies, then copies app files into the user's
# ~/.local hierarchy. No sudo unless the user opts in for apt installs.
#
# Supported package managers: apt (Debian/Ubuntu/Pop), dnf (Fedora),
# pacman (Arch), zypper (openSUSE). On other distros the installer prints
# the generic dependency list and exits the dependency phase.
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

# --- distro detection -----------------------------------------------------
PKG_MGR=""
for mgr in apt dnf pacman zypper; do
    if command -v "$mgr" >/dev/null 2>&1; then
        PKG_MGR="$mgr"
        break
    fi
done
ok "Detected package manager: ${PKG_MGR:-none}"

# Pick a capture backend hint based on the running desktop. Selection at
# runtime is in share/_capture_backend.py — this is just for the install msg.
DESKTOP="${XDG_CURRENT_DESKTOP:-unknown}"
case "${DESKTOP^^}" in
    *COSMIC*)             CAPTURE_HINT="cosmic-screenshot" ;;
    *KDE*|*PLASMA*)       CAPTURE_HINT="spectacle" ;;
    *GNOME*)              CAPTURE_HINT="gnome-screenshot (or grim on Wayland)" ;;
    *SWAY*|*HYPRLAND*)    CAPTURE_HINT="grim" ;;
    *)                    CAPTURE_HINT="grim (Wayland) or maim (X11)" ;;
esac
info "Detected desktop: $DESKTOP — recommended capture backend: $CAPTURE_HINT"

# --- runtime deps ---------------------------------------------------------
# Required: at least one full-screen capture binary, slurp, GTK4/libadwaita
# Python bindings, libnotify, Pillow. Optional: wl-clipboard, rclone, satty.

missing_capture=true
for bin in cosmic-screenshot grim gnome-screenshot spectacle maim; do
    if command -v "$bin" >/dev/null 2>&1; then
        ok "Capture backend present: $bin"
        missing_capture=false
        break
    fi
done

print_apt_packages() {
    cat <<'EOF'
  Required (apt):
    sudo apt install slurp python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
                     libnotify-bin python3-pil
  Capture backend — pick one (Wayland-first):
    sudo apt install grim                  # wlroots: Sway, Hyprland
    sudo apt install gnome-screenshot      # GNOME (Ubuntu default)
    sudo apt install kde-spectacle         # KDE Plasma
    sudo apt install cosmic-screenshot     # Pop!_OS / COSMIC
    sudo apt install maim                  # X11 fallback
  Optional:
    sudo apt install wl-clipboard rclone   # clipboard image + Drive sync
EOF
}

print_dnf_packages() {
    cat <<'EOF'
  Required (dnf):
    sudo dnf install slurp python3-gobject gtk4 libadwaita \
                     libnotify python3-pillow
  Capture backend — pick one:
    sudo dnf install grim                  # wlroots
    sudo dnf install gnome-screenshot      # GNOME
    sudo dnf install spectacle             # KDE Plasma
    sudo dnf install maim                  # X11 fallback
  Optional:
    sudo dnf install wl-clipboard rclone
EOF
}

print_pacman_packages() {
    cat <<'EOF'
  Required (pacman):
    sudo pacman -S slurp python-gobject gtk4 libadwaita \
                   libnotify python-pillow
  Capture backend — pick one:
    sudo pacman -S grim                    # wlroots
    sudo pacman -S gnome-screenshot        # GNOME
    sudo pacman -S spectacle               # KDE Plasma
    sudo pacman -S maim                    # X11 fallback
  Optional:
    sudo pacman -S wl-clipboard rclone
EOF
}

print_zypper_packages() {
    cat <<'EOF'
  Required (zypper):
    sudo zypper install slurp python3-gobject typelib-1_0-Gtk-4_0 \
                        typelib-1_0-Adw-1 libnotify-tools python3-Pillow
  Capture backend — pick one:
    sudo zypper install grim
    sudo zypper install gnome-screenshot
    sudo zypper install spectacle
    sudo zypper install maim
  Optional:
    sudo zypper install wl-clipboard rclone
EOF
}

print_generic_packages() {
    cat <<'EOF'
  Generic dependency list (install via your package manager):
    Required: slurp, python3 + GObject introspection (GTK 4, libadwaita 1),
              libnotify, Pillow / python3-pil
    Capture: one of cosmic-screenshot, grim, gnome-screenshot, spectacle, maim
    Optional: wl-clipboard, rclone
EOF
}

# Build apt list dynamically only on Debian-family
APT_NEEDED=()
if [[ "$PKG_MGR" == "apt" ]]; then
    for pkg in slurp python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
               libnotify-bin python3-pil; do
        case "$pkg" in
            slurp)         command -v slurp     >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
            libnotify-bin) command -v notify-send >/dev/null 2>&1 || APT_NEEDED+=("$pkg") ;;
            python3-pil)   python3 -c "import PIL" 2>/dev/null   || APT_NEEDED+=("$pkg") ;;
            *)             dpkg -s "$pkg" >/dev/null 2>&1        || APT_NEEDED+=("$pkg") ;;
        esac
    done
fi

if [[ "$PKG_MGR" == "apt" && ${#APT_NEEDED[@]} -gt 0 ]]; then
    warn "Missing apt packages: ${APT_NEEDED[*]}"
    read -rp "Install them now with sudo apt? [Y/n] " ans
    if [[ -z "$ans" || "$ans" =~ ^[Yy] ]]; then
        sudo apt update
        sudo apt install -y "${APT_NEEDED[@]}"
    else
        warn "Skipping apt install — install them manually before first run."
    fi
elif [[ "$PKG_MGR" == "apt" ]]; then
    ok "All apt dependencies present"
fi

if $missing_capture; then
    warn "No capture backend found on PATH. Install one of:"
    case "$PKG_MGR" in
        apt)    print_apt_packages ;;
        dnf)    print_dnf_packages ;;
        pacman) print_pacman_packages ;;
        zypper) print_zypper_packages ;;
        *)      print_generic_packages ;;
    esac
fi

# --- recorder (gpu-screen-recorder, flatpak system-wide) ------------------
if command -v flatpak >/dev/null 2>&1; then
    if ! flatpak list --system --app 2>/dev/null | grep -q com.dec05eba.gpu_screen_recorder; then
        warn "gpu-screen-recorder flatpak (recommended for Record) not installed."
        warn "User installs are broken — must be system-wide."
        read -rp "Install com.dec05eba.gpu_screen_recorder system-wide? [y/N] " ans
        if [[ "$ans" =~ ^[Yy] ]]; then
            sudo flatpak remote-add --if-not-exists flathub \
                https://dl.flathub.org/repo/flathub.flatpakrepo
            sudo flatpak install --system -y flathub com.dec05eba.gpu_screen_recorder
        fi
    else
        ok "gpu-screen-recorder flatpak present"
    fi
else
    warn "flatpak not installed — Record button will not work without it."
    warn "  Install flatpak via your package manager, then re-run this installer."
fi

# --- annotation (Satty, optional) -----------------------------------------
satty_present=false
command -v satty >/dev/null 2>&1 && satty_present=true
if ! $satty_present && command -v flatpak >/dev/null 2>&1 \
        && flatpak info org.satty.Satty >/dev/null 2>&1; then
    satty_present=true
fi
if ! $satty_present; then
    warn "Satty (annotation editor) not installed — Annotate button will fail."
    warn "  Easiest path: download satty-vX.Y.Z.flatpak from"
    warn "  https://github.com/Satty-org/Satty/releases and run:"
    warn "    flatpak install --user /path/to/satty-vX.Y.Z.flatpak"
    warn "  See README for cargo / distro-package alternatives."
else
    ok "Satty present"
fi

# --- copy files -----------------------------------------------------------
mkdir -p "$BIN_DIR" "$SHARE_DIR" "$APPS_DIR" "$CONFIG_DIR"
install -m 755 "$REPO_DIR/bin/cosmic-capture"           "$BIN_DIR/cosmic-capture"
install -m 644 "$REPO_DIR/share/_capture_backend.py"    "$SHARE_DIR/_capture_backend.py"
install -m 755 "$REPO_DIR/share/overlay.py"             "$SHARE_DIR/overlay.py"
install -m 755 "$REPO_DIR/share/screenshot.py"          "$SHARE_DIR/screenshot.py"
install -m 755 "$REPO_DIR/share/annotate.py"            "$SHARE_DIR/annotate.py"
install -m 755 "$REPO_DIR/share/record.py"              "$SHARE_DIR/record.py"
install -m 755 "$REPO_DIR/share/recorder_hud.py"        "$SHARE_DIR/recorder_hud.py"
install -m 755 "$REPO_DIR/share/sync_and_share.py"      "$SHARE_DIR/sync_and_share.py"
install -m 644 "$REPO_DIR/applications/cosmic-capture.desktop" "$APPS_DIR/cosmic-capture.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true
ok "Files installed"

# --- config ---------------------------------------------------------------
if [[ ! -f "$CONFIG_DIR/config.ron" ]]; then
    cp "$REPO_DIR/config/config.ron.example" "$CONFIG_DIR/config.ron"
    sed -i "s|/home/YOU|$HOME|g" "$CONFIG_DIR/config.ron"
    ok "Default config written to $CONFIG_DIR/config.ron"
else
    ok "Existing config.ron kept — review against config.ron.example if upgrading"
fi

# --- capture folders ------------------------------------------------------
mkdir -p "$HOME/Pictures/Screenshots" "$HOME/Videos/Screenrecordings"

# --- next steps -----------------------------------------------------------
cat <<EOF

Next steps:

1. Bind a keyboard shortcut to:  gtk-launch cosmic-capture
   (Use 'gtk-launch', not the binary path — see README "Known quirks".)

2. Pin to dock (optional, COSMIC):
   Edit ~/.config/cosmic/com.system76.CosmicAppList/v1/favorites
   and add:   "cosmic-capture",
   Then: pkill cosmic-panel

3. Google Drive sync (optional, screen recordings only):
   rclone config         # name the remote per config.ron (default "gdrive")
   Edit $CONFIG_DIR/config.ron and set drive.remote / drive.base_folder.
   Leave drive.base_folder = "" to disable upload.

4. Test:
   gtk-launch cosmic-capture

EOF

ok "Install complete."
