# Changelog

## Unreleased

### Fixed
- **Record produced nothing on NVIDIA.** The `gpu-screen-recorder` flatpak
  needs the GL driver extension matching the *host* NVIDIA driver
  (`org.freedesktop.Platform.GL.nvidia-<driver>`); flatpak does not pull it
  automatically for an already-installed runtime. Without it, EGL inside the
  sandbox falls back to llvmpipe and gsr dies with `failed to load opengl`,
  so every capture mode silently failed. `install.sh` now detects the running
  NVIDIA driver and installs the matching GL extension into the same scope as
  the recorder (no-op on AMD/Intel). `record.py` additionally captures gsr's
  output, detects an immediate exit, and reports the cause (with the GL hint)
  instead of showing a recording HUD over a dead recorder.
- **Annotate lost the result when you clicked Copy.** Satty's toolbar Copy
  button only does `save-to-clipboard`, not `save-to-file`; with `--early-exit`
  that closed Satty without writing the output file, so the host-side clipboard
  copy was skipped — you ended up with nothing on the clipboard *and* no saved
  PNG ("it closes when I copy/save"). `annotate.py` now passes
  `--save-after-copy` so Copy, Save, and Enter all leave a file on disk for the
  host to copy to the clipboard (the host owns the clipboard so it survives
  Satty's exit), plus `--actions-on-escape exit` for a clean cancel.

## 0.3.0 — 2026-05-08

### Added
- **Custom minimalist app icon** (`share/icons/cosmic-capture.svg`) —
  indigo backdrop, four white viewfinder brackets, single red capture
  dot. Installed into the user's `hicolor` theme by `install.sh` and
  referenced from the desktop entry. Replaces the previous
  `camera-photo` system fallback.
- Author / contact info in `LICENSE` and `README.md`
  (Brecht Soenen, dinsdag.xyz).

### Fixed
- **Record on HiDPI / fractionally-scaled monitors.** gpu-screen-recorder
  5.12's `-w region` mode silently downscales the captured stream by the
  inverse of the monitor's scale factor (e.g. on a 150%-scaled display a
  1000×600 selection produced a 250×150 video). `record.py` now detects
  the picked monitor's scale via `cosmic-randr`; on scaled monitors it
  captures the full monitor at correct physical resolution and crops to
  the requested region with `ffmpeg` after the recorder exits. Unscaled
  monitors keep the fast native path.
- Desktop entry no longer hardcodes `/home/brecht/.local/bin/...`; the
  installer pins `$HOME/.local/bin/cosmic-capture` per machine.

### Changed
- `cosmic-capture.desktop` adds `Keywords`, `GenericName`, broader
  `Categories` (`Utility;Graphics;AudioVideo;Recorder`) and
  `StartupNotify=true` so it surfaces in launcher search.

## 0.2.0 — staging

### Added
- **Annotate button** in the popup, powered by [Satty](https://github.com/Satty-org/Satty).
  Captures a region, hands the cropped PNG to Satty for arrows / blur /
  text, then saves + copies to clipboard on Enter.
- **Pluggable capture backend** (`share/_capture_backend.py`): auto-detects
  `cosmic-screenshot`, `grim`, `gnome-screenshot`, `spectacle`, or `maim`
  based on `XDG_CURRENT_DESKTOP` and binary availability.
- **Year-month subfolders** for screenshot output: captures land under
  `<screenshot_dir>/YYYYMM/` instead of one flat directory.
- **Image-to-clipboard on save** for Screenshot — paste straight into
  Slack/Gmail/etc.
- **Hotkeys**: `S` / `A` / `R` (or `1` / `2` / `3`) inside the popup.
- **Multi-distro installer**: detects apt / dnf / pacman / zypper and
  prints distro-appropriate dependency commands. apt is auto-installed on
  user consent.
- `CONTRIBUTING.md`, issue templates, PR template.

### Changed
- README rewritten for cross-desktop use; supported-desktop matrix added.
- Drive sync no longer triggered for screenshots — only for screen
  recordings (where it's still useful).

### Notes
- Project name kept as `cosmic-capture` for now even though it's broader.
  Rename open for discussion in a follow-up.
