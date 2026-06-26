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

from screenshot import capture_fullscreen, cfg, notify, open_folder, pick_region


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

        # Clipboard handoff strategy: the HOST owns the clipboard, never
        # Satty. We deliberately do NOT pass --copy-command: flatpak Satty
        # has no wl-copy in its sandbox and its only escape hatch
        # (flatpak-spawn --host) needs a Flatpak-bus permission Satty doesn't
        # ship with. Satty's built-in save-to-clipboard works inside the
        # sandbox but the clipboard is torn down the instant Satty exits —
        # so on every exit path we instead make Satty write the PNG to
        # out_path and copy that file from the host afterwards (wl-copy
        # daemonizes and survives Satty + the popup tear-down).
        #
        # The catch the previous version missed: Satty's toolbar **Copy**
        # button only does save-to-clipboard, NOT save-to-file. With
        # --early-exit that closed Satty without ever writing out_path, so
        # the host-side copy below was skipped and the user lost both the
        # clipboard *and* the file — "it closes when I copy". --save-after-copy
        # forces a copy to also write out_path, so Copy, Save, and Enter all
        # leave a file for the host to pick up. Escape exits without saving
        # (clean cancel: no out_path → host does nothing).
        cmd = [
            *satty,
            "--filename", crop_path,
            "--output-filename", out_path,
            "--actions-on-enter", "save-to-file,exit",
            "--actions-on-escape", "exit",
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

    # Copy from the host so the clipboard survives Satty's exit. wl-copy
    # daemonizes after reading stdin and serves clipboard requests until
    # something else takes over — surviving us, Satty, and the popup tear-down.
    try:
        with open(out_path, "rb") as f:
            subprocess.run(
                ["wl-copy", "--type", "image/png"],
                stdin=f, check=False,
            )
    except FileNotFoundError:
        logging.warning("wl-copy not installed; clipboard skipped")

    open_folder(save_dir)
    notify("Annotation saved", f"{out_path}\nCopied to clipboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
