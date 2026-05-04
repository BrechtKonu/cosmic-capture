#!/usr/bin/env python3
"""Region screenshot → Satty annotation editor.

Same slurp + capture-backend + crop flow as screenshot.py, but the cropped
PNG is handed to Satty for annotation. Satty handles save + clipboard via
its own flags; we open the destination folder afterwards.

Satty is auto-detected: native `satty` on PATH wins; otherwise the
`org.satty.Satty` flatpak is used.
"""
import datetime as _dt
import logging
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

from screenshot import capture_fullscreen, cfg, notify, pick_region


def _satty_command() -> list[str] | None:
    if shutil.which("satty"):
        return ["satty"]
    if shutil.which("flatpak"):
        r = subprocess.run(
            ["flatpak", "info", "org.satty.Satty"],
            capture_output=True,
        )
        if r.returncode == 0:
            return ["flatpak", "run", "org.satty.Satty"]
    return None

LOG_PATH = "/tmp/cosmic-capture-annotate.log"
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)


def main() -> int:
    base_dir = cfg("screenshot_dir") or os.path.expanduser("~/Pictures/Screenshots")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
    now = _dt.datetime.now()
    save_dir = os.path.join(base_dir, now.strftime("%Y%m"))
    os.makedirs(save_dir, exist_ok=True)
    logging.info("annotate start — save_dir=%s", save_dir)

    region = pick_region()
    if region is None:
        return 0
    x, y, w, h = region

    # Flatpak Satty's sandbox only sees $HOME (filesystems=home), not /tmp.
    cache_root = os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
        "cosmic-capture",
    )
    os.makedirs(cache_root, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="annotate-", dir=cache_root) as td:
        full = capture_fullscreen(td)
        if not full:
            return 1

        crop_path = os.path.join(td, "crop.png")
        try:
            with Image.open(full) as img:
                img.crop((x, y, x + w, y + h)).save(crop_path, format="PNG")
        except Exception as e:
            logging.exception("crop failed")
            notify("Annotate failed", f"crop error: {e}")
            return 1

        stamp = now.strftime(template)
        out_path = os.path.join(save_dir, f"{stamp}.png")

        satty = _satty_command()
        if satty is None:
            notify(
                "Annotate failed",
                "Satty not installed. See README — install via flatpak, "
                "cargo, or distro package.",
            )
            return 1

        cmd = [
            *satty,
            "--filename", crop_path,
            "--output-filename", out_path,
            "--copy-command", "wl-copy",
            "--actions-on-enter", "save-to-file,save-to-clipboard,exit",
            "--save-after-copy",
            "--early-exit",
            "--initial-tool", "arrow",
        ]
        logging.info("exec %s", cmd)
        r = subprocess.run(cmd)
        logging.info("satty rc=%s", r.returncode)

    if not os.path.exists(out_path):
        # User cancelled inside Satty without saving.
        return 0

    subprocess.Popen(
        ["xdg-open", save_dir],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    notify("Annotation saved", f"{out_path}\nCopied to clipboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
