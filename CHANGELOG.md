# Changelog

## Unreleased — main

### Added
- **Custom app icon** (`share/icons/cosmic-capture.svg`) — installed into
  the user's `hicolor` theme by `install.sh` and referenced from the
  desktop entry. Replaces the previous `camera-photo` system fallback.
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
