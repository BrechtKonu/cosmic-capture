#!/usr/bin/env python3
"""Region / full-screen screenshot for COSMIC.

COSMIC's compositor does not implement wlr-screencopy, so grim doesn't work.
Flow:
  - Optional countdown delay
  - slurp picks a region (or skipped for full-screen mode)
  - cosmic-screenshot (xdg-desktop-portal-cosmic) writes a full capture to a
    temp dir; PIL crops to the slurp geometry when in region mode
  - Optional pass through `satty` for annotation
  - Save to disk and copy PNG to the Wayland clipboard
  - Trigger Drive sync (if configured)
"""
import argparse
import datetime as _dt
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

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


def cfg_bool(key: str, default: bool = False) -> bool:
    v = cfg(key, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def notify(summary: str, body: str = "") -> None:
    subprocess.Popen(
        ["notify-send", "-a", "Cosmic Capture", summary, body],
        start_new_session=True,
    )


def pick_region() -> tuple[int, int, int, int] | None:
    # Allow the overlay window to fully tear down before slurp grabs input.
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


def annotate(in_path: str, out_path: str) -> bool:
    """Open satty for annotation. Returns True if a result file was produced."""
    if not shutil.which("satty"):
        notify(
            "Annotation skipped",
            "Install 'satty' to enable: https://github.com/gabm/satty",
        )
        return False
    cmd = [
        "satty",
        "--filename", in_path,
        "--output-filename", out_path,
        "--early-exit",
    ]
    if shutil.which("wl-copy"):
        cmd += ["--copy-command", "wl-copy -t image/png"]
    r = subprocess.run(cmd)
    logging.info("satty rc=%s", r.returncode)
    return r.returncode == 0 and os.path.exists(out_path)


def copy_to_clipboard(path: str) -> bool:
    if not shutil.which("wl-copy"):
        logging.warning("wl-copy not installed; skipping clipboard copy")
        return False
    try:
        with open(path, "rb") as f:
            r = subprocess.run(
                ["wl-copy", "--type", "image/png"],
                stdin=f,
                check=False,
            )
        return r.returncode == 0
    except OSError as e:
        logging.warning("clipboard copy failed: %s", e)
        return False


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cosmic Capture screenshot")
    p.add_argument(
        "--mode",
        choices=("region", "full"),
        default=None,
        help="region (slurp) or full (entire focused output)",
    )
    p.add_argument(
        "--delay",
        type=int,
        default=None,
        help="seconds to wait before capture",
    )
    p.add_argument(
        "--annotate",
        action="store_true",
        default=False,
        help="open satty for annotation after capture",
    )
    p.add_argument(
        "--no-clipboard",
        action="store_true",
        default=False,
        help="skip copy-to-clipboard step",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    save_dir = cfg("screenshot_dir") or os.path.expanduser("~/Pictures/Screenshots")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
    os.makedirs(save_dir, exist_ok=True)

    mode = args.mode or cfg("default_mode", "region")
    if mode not in ("region", "full"):
        mode = "region"
    delay = args.delay if args.delay is not None else int(cfg("default_delay", "0") or "0")
    do_annotate = args.annotate or cfg_bool("annotate_default", False)
    do_clipboard = (not args.no_clipboard) and cfg_bool("clipboard", True)

    logging.info(
        "screenshot start mode=%s delay=%s annotate=%s clipboard=%s save_dir=%s",
        mode, delay, do_annotate, do_clipboard, save_dir,
    )

    region: tuple[int, int, int, int] | None = None
    if mode == "region":
        region = pick_region()
        if region is None:
            return 0  # user cancelled

    if delay > 0:
        notify("Capturing", f"in {delay}s")
        time.sleep(delay)

    with tempfile.TemporaryDirectory(prefix="cosmic-capture-") as td:
        full = capture_fullscreen(td)
        if not full:
            return 1

        stamp = _dt.datetime.now().strftime(template)
        out_path = unique_path(os.path.join(save_dir, f"{stamp}.png"))

        try:
            with Image.open(full) as img:
                if region is not None:
                    x, y, w, h = region
                    img = img.crop((x, y, x + w, y + h))
                img.save(out_path, format="PNG")
        except Exception as e:
            logging.exception("save/crop failed")
            notify("Screenshot failed", f"image error: {e}")
            return 1

        if do_annotate:
            annotated_path = unique_path(
                os.path.join(save_dir, f"{stamp}_annotated.png")
            )
            if annotate(out_path, annotated_path):
                out_path = annotated_path

    if do_clipboard:
        copy_to_clipboard(out_path)

    body = out_path + ("  ·  copied to clipboard" if do_clipboard else "")
    notify("Screenshot saved", body)

    helper_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.Popen(
        [sys.executable, os.path.join(helper_dir, "sync_and_share.py"),
         "screenshot", out_path],
        start_new_session=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
