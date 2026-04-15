#!/usr/bin/env python3
"""Region screenshot for COSMIC.

COSMIC's compositor does not implement wlr-screencopy, so grim doesn't work.
Flow: slurp picks a region, cosmic-screenshot (via xdg-desktop-portal-cosmic)
captures the full screen to a temp file, PIL crops to the slurp geometry,
and the result is saved to the configured screenshot directory.
"""
import datetime as _dt
import logging
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

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
    try:
        r = subprocess.run(
            [
                "cosmic-screenshot",
                "--interactive=false",
                "--notify=false",
                "--save-dir", dest_dir,
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        notify("Screenshot failed", "cosmic-screenshot not installed")
        return None
    logging.info(
        "cosmic-screenshot rc=%s stdout=%r stderr=%r",
        r.returncode, r.stdout, r.stderr,
    )
    if r.returncode != 0:
        notify("Screenshot failed", r.stderr.strip() or "capture exited non-zero")
        return None
    path = r.stdout.strip()
    return path if os.path.exists(path) else None


def main() -> int:
    save_dir = cfg("screenshot_dir") or os.path.expanduser("~/Pictures/Screenshots")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
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

        stamp = _dt.datetime.now().strftime(template)
        out_path = os.path.join(save_dir, f"{stamp}.png")

        try:
            with Image.open(full) as img:
                cropped = img.crop((x, y, x + w, y + h))
                cropped.save(out_path, format="PNG")
        except Exception as e:
            logging.exception("crop failed")
            notify("Screenshot failed", f"crop error: {e}")
            return 1

    notify("Screenshot saved", out_path)

    helper_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.Popen(
        [sys.executable, os.path.join(helper_dir, "sync_and_share.py"),
         "screenshot", out_path],
        start_new_session=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
