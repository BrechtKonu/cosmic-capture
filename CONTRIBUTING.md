# Contributing to Cosmic Capture

Thanks for considering a contribution. The project is small enough that
most changes can land via a single PR — no big design ceremony needed.

## Before you start

- For anything bigger than a one-line fix, **open an issue first** and
  describe what you want to change. Saves you from rebuilding work that
  doesn't fit the project's direction.
- The project deliberately stays small. New features should be optional
  or behind a config flag, not "grow the popup".

## Setup

```bash
git clone https://github.com/BrechtKonu/cosmic-capture.git
cd cosmic-capture
./install.sh
```

Edits to files in `share/` go into the source tree. After editing, re-run
`./install.sh` to copy them into `~/.local/share/cosmic-capture/` — that's
where the running app reads from.

To iterate faster while developing, you can symlink instead:

```bash
ln -sf "$PWD/share/screenshot.py" ~/.local/share/cosmic-capture/screenshot.py
# repeat for any file you're hacking on
```

## Branch naming

```
<your-handle>-<short-topic>
```

Examples: `brecht-grim-fallback`, `kris-kde-spectacle-flags`,
`alex-fix-recording-hud`. One topic per branch — don't bundle unrelated
changes.

If you're internal to Konu, follow the project rule (`<INITIALS>-<TICKET>`)
from your `~/claude-rules/CLAUDE.md`. External contributors can use any
short, descriptive slug.

## Commit messages

Keep them short and direct. Subject line under ~70 chars; body if you
need to explain *why*.

External contributors can use plain Conventional-Commits-ish style:

```
fix: grim falls back to maim when wlr-screencopy missing
feat(annotate): allow custom satty initial-tool via config
docs: KDE Plasma keyboard shortcut steps
```

Konu-internal commits follow the `[TASK]/[TICKET] - REF [TYPE] description`
format from `~/claude-rules/rules/commit-conventions.md`.

## Pull request flow

1. Branch off `main`.
2. Push to your fork (or to a branch in this repo if you have write access).
3. Open a PR against `main`. Fill in the template — what you changed and
   how to test it on at least one desktop.
4. CI is intentionally minimal. Reviewers will manually exercise the
   capture flow on their own desktop before merging.

## What's easy to contribute

- **Test reports for desktops we don't own.** Open a PR adding the desktop
  to the support matrix in `README.md` once it works for you.
- **Capture backends.** Add to `share/_capture_backend.py` — one function,
  one entry in `BACKENDS`, optionally a `_DESKTOP_PREFERENCE` mapping.
- **Per-distro install instructions.** PRs welcome to expand
  `install.sh` and the README's per-distro sections.

## Style

- Python: stdlib + Pillow + PyGObject only. Keep the dependency footprint
  minimal — this should still install with one apt/dnf/pacman line.
- Bash: `set -euo pipefail`, no Bashisms beyond what stock Ubuntu's bash
  understands.
- No mass reformatting in feature PRs — keep diffs reviewable.

## Reporting bugs

Use the [bug template](.github/ISSUE_TEMPLATE/bug.md). Include:

1. Distro + version (`cat /etc/os-release`)
2. Desktop (`echo $XDG_CURRENT_DESKTOP`)
3. Whether you're on Wayland or X11 (`echo $XDG_SESSION_TYPE`)
4. Logs from `/tmp/cosmic-capture-*.log`
5. Steps to reproduce.

## License

By contributing you agree your work is licensed under the project's MIT
license.
