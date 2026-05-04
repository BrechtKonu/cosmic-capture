#!/usr/bin/env python3
"""Region screenshot.

Flow: slurp picks a region, a desktop-appropriate backend (cosmic-screenshot,
grim, gnome-screenshot, spectacle, maim) captures the full screen to a temp
file, PIL crops to the slurp geometry, and the result is saved to the
configured screenshot directory under a YYYYMM subfolder.

The backend is auto-detected from XDG_CURRENT_DESKTOP and falls back to the
first installed binary in BACKENDS. See _capture_backend.py.
"""
import datetime as _dt
import logging
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

from _capture_backend import capture_fullscreen as _backend_capture

LOG_PATH = "/tmp/cosmic-capture-screenshot.log"
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

GEOM_RE = re.compile(r"^(?P<x>\d+),(?P<y>\d+)\s+(?P<w>\d+)x(?P<h>\d+)$")


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(f"COSMIC_CAPTURE_{key.upper()}", default)


def notify(summary: str, body: str = "") -> None:
    subprocess.Popen(
        ["notify-send", "-a", "Cosmic Capture", summary, body],
        start_new_session=True,
    )


def pick_region() -> tuple[int, int, int, int] | None:
    import time
    time.sleep(0.25)
    try:
        r = subprocess.run(
            ["slurp", "-f", "%x,%y %wx%h"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        notify("Screenshot failed", "slurp not installed")
        return None
    logging.info("slurp rc=%s stdout=%r stderr=%r", r.returncode, r.stdout, r.stderr)
    if r.returncode != 0:
        return None
    m = GEOM_RE.match(r.stdout.strip())
    if not m:
        notify("Screenshot failed", f"bad slurp output: {r.stdout!r}")
        return None
    return int(m["x"]), int(m["y"]), int(m["w"]), int(m["h"])


def capture_fullscreen(dest_dir: str) -> str | None:
    path = _backend_capture(dest_dir)
    if not path:
        notify(
            "Screenshot failed",
            "No capture backend available — install one of: "
            "cosmic-screenshot, grim, gnome-screenshot, spectacle, maim",
        )
    return path


def main() -> int:
    base_dir = cfg("screenshot_dir") or os.path.expanduser("~/Pictures/Screenshots")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
    now = _dt.datetime.now()
    save_dir = os.path.join(base_dir, now.strftime("%Y%m"))
    os.makedirs(save_dir, exist_ok=True)
    logging.info("screenshot start — save_dir=%s", save_dir)

    region = pick_region()
    if region is None:
        return 0
    x, y, w, h = region

    with tempfile.TemporaryDirectory(prefix="cosmic-capture-") as td:
        full = capture_fullscreen(td)
        if not full:
            return 1

        stamp = now.strftime(template)
        out_path = os.path.join(save_dir, f"{stamp}.png")

        try:
            with Image.open(full) as img:
                cropped = img.crop((x, y, x + w, y + h))
                cropped.save(out_path, format="PNG")
        except Exception as e:
            logging.exception("crop failed")
            notify("Screenshot failed", f"crop error: {e}")
            return 1

    try:
        with open(out_path, "rb") as f:
            subprocess.run(
                ["wl-copy", "--type", "image/png"],
                stdin=f, check=False,
            )
    except FileNotFoundError:
        logging.warning("wl-copy not installed; clipboard skipped")

    subprocess.Popen(
        ["xdg-open", save_dir],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    notify("Screenshot saved", f"{out_path}\nCopied to clipboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
