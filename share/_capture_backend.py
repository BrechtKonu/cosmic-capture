"""Pluggable full-screen capture backend.

Each backend writes a PNG of the full screen into a destination directory and
returns its path. The first backend whose binary is installed wins, with a
preference order biased toward the running desktop. To add a backend, append
to BACKENDS — order matters.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Backend:
    name: str
    binary: str
    capture: Callable[[str], str | None]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _cosmic(dest_dir: str) -> str | None:
    r = _run([
        "cosmic-screenshot",
        "--interactive=false", "--notify=false",
        "--save-dir", dest_dir,
    ])
    logging.info("cosmic-screenshot rc=%s stderr=%r", r.returncode, r.stderr)
    if r.returncode != 0:
        return None
    path = r.stdout.strip()
    return path if path and os.path.exists(path) else None


def _path_in(dest_dir: str, suffix: str = "fullscreen.png") -> str:
    fd, path = tempfile.mkstemp(prefix="cap-", suffix=f"-{suffix}", dir=dest_dir)
    os.close(fd)
    return path


def _grim(dest_dir: str) -> str | None:
    out = _path_in(dest_dir)
    r = _run(["grim", out])
    logging.info("grim rc=%s stderr=%r", r.returncode, r.stderr)
    return out if r.returncode == 0 and os.path.exists(out) else None


def _gnome(dest_dir: str) -> str | None:
    out = _path_in(dest_dir)
    # -f writes a PNG; on Wayland this routes through xdg-desktop-portal-gnome.
    r = _run(["gnome-screenshot", "-f", out])
    logging.info("gnome-screenshot rc=%s stderr=%r", r.returncode, r.stderr)
    return out if r.returncode == 0 and os.path.exists(out) else None


def _spectacle(dest_dir: str) -> str | None:
    out = _path_in(dest_dir)
    # -b background, -n no notification, -f fullscreen, -o output path
    r = _run(["spectacle", "-b", "-n", "-f", "-o", out])
    logging.info("spectacle rc=%s stderr=%r", r.returncode, r.stderr)
    return out if r.returncode == 0 and os.path.exists(out) else None


def _maim(dest_dir: str) -> str | None:
    out = _path_in(dest_dir)
    r = _run(["maim", out])
    logging.info("maim rc=%s stderr=%r", r.returncode, r.stderr)
    return out if r.returncode == 0 and os.path.exists(out) else None


BACKENDS: tuple[Backend, ...] = (
    Backend("cosmic",     "cosmic-screenshot", _cosmic),
    Backend("grim",       "grim",              _grim),
    Backend("gnome",      "gnome-screenshot",  _gnome),
    Backend("spectacle",  "spectacle",         _spectacle),
    Backend("maim",       "maim",              _maim),
)

_DESKTOP_PREFERENCE: dict[str, tuple[str, ...]] = {
    "COSMIC":      ("cosmic", "grim"),
    "GNOME":       ("gnome", "grim"),
    "UBUNTU:GNOME": ("gnome", "grim"),
    "KDE":         ("spectacle", "grim"),
    "PLASMA":      ("spectacle", "grim"),
    "SWAY":        ("grim",),
    "HYPRLAND":    ("grim",),
    "WLROOTS":     ("grim",),
}


def _ordered_backends() -> list[Backend]:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").upper()
    preferred_names: tuple[str, ...] = ()
    for key, names in _DESKTOP_PREFERENCE.items():
        if key in desktop:
            preferred_names = names
            break
    by_name = {b.name: b for b in BACKENDS}
    ordered: list[Backend] = [by_name[n] for n in preferred_names if n in by_name]
    for b in BACKENDS:
        if b not in ordered:
            ordered.append(b)
    return ordered


def select_backend() -> Backend | None:
    """Return the first available backend, biased toward the running desktop."""
    for b in _ordered_backends():
        if shutil.which(b.binary):
            logging.info("capture backend selected: %s", b.name)
            return b
    return None


def capture_fullscreen(dest_dir: str) -> str | None:
    """Capture the full screen into dest_dir; return the saved PNG path."""
    backend = select_backend()
    if backend is None:
        logging.error("no capture backend available")
        return None
    return backend.capture(dest_dir)
