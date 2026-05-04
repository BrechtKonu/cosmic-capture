# Cosmic Capture

A small Wayland-first screenshot, annotation, and screen-recording overlay
for Linux. One keystroke opens a popup with three buttons — **Screenshot**,
**Annotate**, **Record** — each with region selection, auto-save into a
year-month folder, and clipboard handoff.

Originally built for Pop!_OS **COSMIC** (hence the name); now works on any
desktop where one of the supported capture backends is installed.

![overlay](docs/overlay.png) <!-- replace once you have a fresh shot -->

## Why

Compositor-native screenshot tools each have gaps: COSMIC has no recorder,
GNOME has no fast region-annotate flow, and the cross-distro story for
"capture → annotate → paste into Slack" is a pile of half-broken
shell scripts. This wraps the good parts (slurp, your compositor's capture
tool, `gpu-screen-recorder`, Satty) behind one GTK4/libadwaita popup that
you bind to Print Screen.

## Features

- **Three modes from one popup**: Screenshot, Annotate (Satty), Record.
- **Region selection** for all three (slurp).
- **Auto-organized output**: `~/Pictures/Screenshots/YYYYMM/`,
  `~/Videos/Screenrecordings/`.
- **Clipboard on save**: PNG bytes go straight to the Wayland clipboard so
  you can paste into Slack/Gmail/Element/etc.
- **Recording HUD**: floating timer + stop button while recording.
- **Optional Drive sync** for screen recordings via `rclone` — uploads,
  fetches a share link, copies to clipboard, opens Drive's share UI.
- **Pluggable capture backend**: auto-detects the right tool for your
  desktop (COSMIC / GNOME / KDE / wlroots / X11).

## Supported desktops

| Desktop                | Capture backend       | Status                  |
| ---------------------- | --------------------- | ----------------------- |
| Pop!_OS COSMIC         | `cosmic-screenshot`   | Primary target, tested  |
| GNOME (Wayland)        | `gnome-screenshot`    | Works                   |
| KDE Plasma             | `spectacle`           | Works                   |
| Sway / Hyprland (wlroots) | `grim`             | Works                   |
| Any X11 desktop        | `maim`                | Works                   |

The backend is picked at runtime from `XDG_CURRENT_DESKTOP`, falling back
to the first installed binary. To force a specific backend, set
`PATH` so only the one you want is reachable, or open a PR adding an env
override.

## Install

### Quick start

```bash
git clone https://github.com/BrechtKonu/cosmic-capture.git ~/cosmic-capture
cd ~/cosmic-capture
./install.sh
```

The installer:
1. Detects your package manager (apt / dnf / pacman / zypper) and prints
   the exact install command for the missing dependencies.
2. On Debian/Ubuntu/Pop, offers to `sudo apt install` them for you.
3. Copies the app into `~/.local/{bin,share,share/applications}`.
4. Drops a default `config.ron` in `~/.config/cosmic-capture/` if absent.

### Dependencies

| Component                         | Required? | Notes                                          |
| --------------------------------- | --------- | ---------------------------------------------- |
| `slurp`                           | yes       | Region selection                               |
| Capture backend (one of)          | yes       | `cosmic-screenshot`, `grim`, `gnome-screenshot`, `spectacle`, `maim` |
| `python3-gi` + GTK 4 + libadwaita | yes       | The popup                                      |
| `libnotify` (`notify-send`)       | yes       | Toasts                                         |
| `python3-pil` (Pillow)            | yes       | Cropping                                       |
| `wl-clipboard` (`wl-copy`)        | recommended | Image-to-clipboard on save                   |
| `gpu-screen-recorder` (flatpak)   | for Record | System-wide install only — see Quirks         |
| Satty                             | for Annotate | flatpak `org.satty.Satty`, cargo, or distro pkg |
| `rclone`                          | optional  | Drive sync for recordings                      |

#### Per-distro install commands

<details><summary>Debian / Ubuntu / Pop!_OS</summary>

```bash
sudo apt install slurp python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
                 libnotify-bin python3-pil wl-clipboard
# Pick a capture backend:
sudo apt install grim                # wlroots: Sway, Hyprland
sudo apt install gnome-screenshot    # GNOME (Ubuntu default)
sudo apt install kde-spectacle       # KDE Plasma
sudo apt install cosmic-screenshot   # Pop!_OS / COSMIC
sudo apt install maim                # X11 fallback
```

</details>

<details><summary>Fedora</summary>

```bash
sudo dnf install slurp python3-gobject gtk4 libadwaita \
                 libnotify python3-pillow wl-clipboard
sudo dnf install grim                # wlroots
sudo dnf install gnome-screenshot    # GNOME
sudo dnf install spectacle           # KDE Plasma
```

</details>

<details><summary>Arch / Manjaro</summary>

```bash
sudo pacman -S slurp python-gobject gtk4 libadwaita \
               libnotify python-pillow wl-clipboard
sudo pacman -S grim                  # wlroots
sudo pacman -S gnome-screenshot      # GNOME
sudo pacman -S spectacle             # KDE Plasma
```

</details>

<details><summary>openSUSE</summary>

```bash
sudo zypper install slurp python3-gobject typelib-1_0-Gtk-4_0 \
                    typelib-1_0-Adw-1 libnotify-tools python3-Pillow wl-clipboard
sudo zypper install grim
```

</details>

#### Satty (annotation editor)

The Annotate button shells out to [Satty](https://github.com/Satty-org/Satty).
Pick whichever install path is easiest:

```bash
# Flatpak — most reliable across distros, ships its own icon set
flatpak install --user https://github.com/Satty-org/Satty/releases/download/v0.20.1/satty-v0.20.1.flatpak

# Or build from source
cargo install satty

# Or your distro's package, e.g. Arch
sudo pacman -S satty
```

`annotate.py` auto-detects: native `satty` on PATH wins, falling back to
the `org.satty.Satty` flatpak.

#### Recorder

`gpu-screen-recorder` must be installed as the **system** flatpak. The
user-scoped install is broken (the app hardcodes `/var/lib/flatpak`):

```bash
sudo flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
sudo flatpak install --system -y flathub com.dec05eba.gpu_screen_recorder
```

## Configure

`~/.config/cosmic-capture/config.ron` (created on first install):

```ron
(
    screenshot_dir: "/home/YOU/Pictures/Screenshots",
    record_dir:     "/home/YOU/Videos/Screenrecordings",
    filename_template: "%Y-%m-%d_%H-%M-%S",
    recorder: (
        backend: "gpu-screen-recorder-flatpak",
        codec:   "h264",                        // h264 | hevc | av1
        fps:     60,
        audio:   "default_output",              // or "none"
    ),
    overlay: ( close_on_escape: true ),
    drive: (
        remote: "gdrive",                  // rclone remote name; "" disables
        base_folder: "",                   // e.g. "Captures"; "" disables upload
        screenshot_subfolder: "Screenshots",
        recording_subfolder: "Screenrecordings",
    ),
)
```

Captures land under `<screenshot_dir>/YYYYMM/<timestamp>.png` so a year of
screenshots stays browsable.

### Keyboard shortcut

Bind your Print Screen key (or any combo) to:

```
gtk-launch cosmic-capture
```

> ⚠️ Use `gtk-launch`, **not** the binary path. Most compositors put
> children of keyboard bindings in a process context where slurp's
> `wlr-layer-shell` surface silently fails to render. `gtk-launch`
> re-launches into a user systemd scope where it works.

**COSMIC**: see `config/shortcuts.ron` for an example to merge into
`~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom`.

**GNOME**: Settings → Keyboard → Custom Shortcuts → command
`gtk-launch cosmic-capture`. Disable GNOME's built-in Print Screen binding
first.

**KDE**: System Settings → Shortcuts → Custom Shortcuts.

**Sway / Hyprland**: bind in your config to `gtk-launch cosmic-capture`.

### Hotkeys (inside the popup)

| Key      | Action                              |
| -------- | ----------------------------------- |
| `S` or `1` | Screenshot                        |
| `A` or `2` | Annotate                          |
| `R` or `3` | Record                            |
| `Esc`    | Cancel                              |
| Print Screen (while recording) | Stop recording  |

### Pin to dock (COSMIC)

Edit `~/.config/cosmic/com.system76.CosmicAppList/v1/favorites` and add
`"cosmic-capture",` to the array, then `pkill cosmic-panel`.

## Architecture

```
Print Screen / dock click / CLI
    │
    ▼
~/.local/bin/cosmic-capture           (bash entry, parses config.ron → env)
    │
    ├── if recording active → record.py (stop path) → SIGINT to gsr
    │
    └── else → overlay.py              (GTK4/libadwaita popup)
                 │
                 ├── Screenshot → screenshot.py
                 │     slurp → _capture_backend → PIL crop → save → wl-copy → open folder
                 │
                 ├── Annotate  → annotate.py
                 │     slurp → _capture_backend → PIL crop → satty (save+copy) → open folder
                 │
                 └── Record    → record.py
                       slurp → gpu-screen-recorder -w region → PID file + recorder_hud.py
```

`_capture_backend.py` picks the right full-screen capture tool from
`XDG_CURRENT_DESKTOP` and falls back through:
`cosmic-screenshot → grim → gnome-screenshot → spectacle → maim`.

## Logs

Tail these if something silently fails:

```
/tmp/cosmic-capture-overlay.log
/tmp/cosmic-capture-screenshot.log
/tmp/cosmic-capture-annotate.log
/tmp/cosmic-capture-record.log
/tmp/cosmic-capture-sync.log
```

## Known quirks

- **Print Screen binding:** `gtk-launch cosmic-capture`, not the binary
  path — see Keyboard shortcut above.
- **gpu-screen-recorder flatpak:** install `--system`, not `--user`.
- **Satty toolbar icons missing:** happens when your icon theme
  (e.g. COSMIC) doesn't inherit Adwaita's symbolic set. Fix: install
  Satty via flatpak — it ships its own runtime with the right icons.
- **Slurp crosshair flicker on launch:** the 250 ms delay in
  `pick_region()` covers the popup teardown race.
- **Drive folder names** can't contain `/`. If you want the visual effect,
  Google's picker uses a fullwidth slash `／` (U+FF0F).

## Uninstall

```bash
./uninstall.sh           # keeps config + saved captures
./uninstall.sh --purge   # also removes ~/.config/cosmic-capture
```

This does not remove apt packages, flatpaks, your dock favorite, or your
keyboard shortcut. Edit those yourself.

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Especially looking for:

- Verified tests on KDE / Sway / Hyprland / Fedora / Arch.
- A native Rust port of the popup (current GTK4/Python is fine but starts slow).
- An option to skip the popup entirely (one-shot screenshot from a binding).

## License

MIT — see [LICENSE](LICENSE).
