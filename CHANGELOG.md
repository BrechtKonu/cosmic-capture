# Changelog

## Unreleased — staging

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
