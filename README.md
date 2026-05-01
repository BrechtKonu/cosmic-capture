# Cosmic Capture

Screenshot + screen-record overlay for Pop!_OS **COSMIC** desktop, with optional
auto-upload to Google Drive and a one-click share link.

COSMIC ships `cosmic-screenshot` (images only) but no built-in recorder. This
wraps slurp + `cosmic-screenshot` + `gpu-screen-recorder` behind a small
GTK4/libadwaita popup: *Screenshot* and *Record* buttons, each with region
selection, auto-save to configurable folders, and optional Drive sync.

## Features

- **Unified overlay** (screenshot or record) launchable from dock, keyboard
  shortcut, or CLI
- **Capture modes**: region (slurp) or full output (cosmic-screenshot for
  stills, xdg-desktop-portal for recordings)
- **Countdown delay** for screenshots (0 / 3 / 5 s)
- **Auto-copy to clipboard** — every screenshot lands in the Wayland clipboard
  as `image/png`, ready to paste anywhere
- **Annotation** via [`satty`](https://github.com/gabm/satty) — optional
  per-capture; draw, highlight, blur, and save
- **Recording HUD**: floating timer with file-size readout, plus pause/resume
  and stop buttons
- **Microphone capture** alongside system audio (configurable)
- **Auto-save** to configurable folders with timestamp filenames; collisions
  get an `_2`, `_3`, … suffix
- **Optional Drive upload** via rclone — uploads, fetches a share link,
  copies it to clipboard, and opens Drive's share UI in the browser

## Requirements

- Pop!_OS 22.04+ with COSMIC desktop
- `slurp`, `cosmic-screenshot`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`,
  `libnotify-bin`, `python3-pil`, `wl-clipboard` (apt)
- `satty` — optional, enables the annotation step
- `rclone` — optional, for Drive sync
- `gpu-screen-recorder` flatpak — installed **system-wide**
  (user installs are broken: the app hardcodes `/var/lib/flatpak` paths)

The installer offers to install all of these for you.

## Install

```bash
git clone <this-repo> ~/cosmic-capture
cd ~/cosmic-capture
./install.sh
```

## Configure

Edit `~/.config/cosmic-capture/config.ron`:

```ron
(
    screenshot_dir: "/home/YOU/Pictures/Screenshots",
    record_dir:     "/home/YOU/Videos/Screenrecordings",
    filename_template: "%Y-%m-%d_%H-%M-%S",

    clipboard:           true,      // copy each screenshot to the clipboard
    default_mode:        "region",  // region | full     (overlay default)
    default_delay:       0,         // 0 | 3 | 5 seconds
    default_record_mode: "region",  // region | screen
    annotate_default:    false,     // open satty after each screenshot

    recorder: (
        backend: "gpu-screen-recorder-flatpak",
        codec:   "h264",
        fps:     60,
        audio:   "default_output",
        microphone: "none",                   // "default_input" to also record mic
    ),
    overlay: ( close_on_escape: true ),
    drive: (
        remote: "gdrive",                  // rclone remote name
        base_folder: "",                   // "" disables upload
        screenshot_subfolder: "Screenshots",
        recording_subfolder: "Screenrecordings",
    ),
)
```

### Annotation (satty)

If `satty` is on `$PATH` and you tick **Annotate** in the overlay (or set
`annotate_default: true`), the screenshot opens in satty after capture. Save
inside satty and the annotated PNG replaces the unannotated one on disk and
in the clipboard.

Install satty with `cargo install satty` or from the
[releases page](https://github.com/gabm/satty/releases).

### Drive sync (optional)

```bash
rclone config     # create a Google Drive remote; name it to match config.ron
```

Then set `drive.base_folder` in config.ron to the path inside Drive where you
want captures to land (e.g. `"Captures"`). Leave it empty to skip upload.

> ⚠️ Drive folder names can't contain `/`. If you want the visual effect,
> Google's picker uses a fullwidth slash `／` (U+FF0F) — paste that in.

### Pin to dock

```
~/.config/cosmic/com.system76.CosmicAppList/v1/favorites
```

Add `"cosmic-capture",` to the array, then `pkill cosmic-panel`.

### Keyboard shortcut

Merge `config/shortcuts.ron` into
`~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom`. Log out/in
(or restart `cosmic-settings-daemon`) for cosmic-comp to pick it up.

**Important:** the binding uses `gtk-launch cosmic-capture` — **not** the
binary path directly. cosmic-comp's `Spawn` action puts children in a process
context where `slurp`'s `wlr-layer-shell` surface silently fails to render;
`gtk-launch` re-launches into a user systemd scope where it works.

## Architecture

```
Print Screen / dock click / CLI
    │
    ▼
~/.local/bin/cosmic-capture          (bash entry, parses config.ron → env)
    │
    ├── if recording active → record.py (stop path) → SIGINT to gsr → sync
    │
    └── else → overlay.py             (GTK4/libadwaita, Screenshot / Record)
                 │
                 ├── Screenshot → screenshot.py
                 │     slurp → cosmic-screenshot → PIL crop → save → sync
                 │
                 └── Record → record.py (start path)
                       slurp → gpu-screen-recorder -w region → PID file
                                                               + recorder_hud.py
```

Drive sync (`sync_and_share.py`) runs detached after each save:

```
rclone copy → rclone link → wl-copy → xdg-open (Drive share page) → notify
```

## Logs

- `/tmp/cosmic-capture-overlay.log`
- `/tmp/cosmic-capture-screenshot.log`
- `/tmp/cosmic-capture-record.log`
- `/tmp/cosmic-capture-sync.log`

## Uninstall

```bash
./uninstall.sh           # keeps config
./uninstall.sh --purge   # removes config too
```

## Known quirks

- **Print Screen key:** bind via `gtk-launch cosmic-capture`, not the binary
  directly (see above).
- **gpu-screen-recorder flatpak:** install `--system`, not `--user`.
- **Recording region on Wayland:** `slurp` must be visible. If the overlay is
  still closing when slurp starts, you'll see the crosshair briefly — the
  250 ms delay in `screenshot.py` covers the overlay teardown race.

## License

MIT
