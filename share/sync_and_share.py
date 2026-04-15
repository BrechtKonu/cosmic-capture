#!/usr/bin/env python3
"""Upload a capture file to Google Drive, grab a share link, and open Drive's
share UI in a browser.

Usage:
    sync_and_share.py <screenshot|recording> <local_path> [wait_for_pid]

If wait_for_pid is given, block until that PID exits (max 30s) before uploading
— used by record.py so we don't upload a half-finalized mp4.
"""
import logging
import os
import subprocess
import sys
import time

LOG_PATH = "/tmp/cosmic-capture-sync.log"
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

REMOTE = os.environ.get("COSMIC_CAPTURE_DRIVE_REMOTE", "gdrive")
DRIVE_BASE = os.environ.get("COSMIC_CAPTURE_DRIVE_BASE", "")
SCREENSHOT_SUB = os.environ.get("COSMIC_CAPTURE_DRIVE_SCREENSHOT_SUB", "Screenshots")
RECORDING_SUB = os.environ.get("COSMIC_CAPTURE_DRIVE_RECORDING_SUB", "Screenrecordings")


def _dest(sub: str) -> str:
    return f"{DRIVE_BASE}/{sub}" if DRIVE_BASE else sub


DEST_BY_KIND = {
    "screenshot": _dest(SCREENSHOT_SUB),
    "recording":  _dest(RECORDING_SUB),
}


def notify(summary: str, body: str = "") -> None:
    subprocess.Popen(
        ["notify-send", "-a", "Cosmic Capture", summary, body],
        start_new_session=True,
    )


def wait_for_exit(pid: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.3)
    logging.warning("pid %d still alive after %.1fs, proceeding anyway", pid, timeout)


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in DEST_BY_KIND:
        logging.error("bad args: %r", sys.argv)
        return 2

    kind = sys.argv[1]
    path = sys.argv[2]
    if len(sys.argv) >= 4:
        try:
            wait_for_exit(int(sys.argv[3]))
            # small grace period for final flush after process exit
            time.sleep(0.5)
        except ValueError:
            pass

    if not os.path.exists(path):
        logging.error("file missing: %s", path)
        notify("Upload skipped", f"file missing: {path}")
        return 1

    dest_dir = DEST_BY_KIND[kind]
    remote_target = f"{REMOTE}:{dest_dir}"
    filename = os.path.basename(path)

    if not DRIVE_BASE and not SCREENSHOT_SUB and not RECORDING_SUB:
        logging.info("drive sync disabled (no destination configured)")
        return 0

    notify("Uploading to Drive", filename)
    logging.info("copy %s → %s", path, remote_target)
    r = subprocess.run(
        ["rclone", "copy", path, remote_target],
        capture_output=True, text=True,
    )
    logging.info("copy rc=%s stderr=%r", r.returncode, r.stderr)
    if r.returncode != 0:
        notify("Upload failed", r.stderr.strip() or "rclone copy failed")
        return 1

    remote_file = f"{REMOTE}:{dest_dir}/{filename}"
    r = subprocess.run(
        ["rclone", "link", remote_file],
        capture_output=True, text=True,
    )
    logging.info("link rc=%s stdout=%r stderr=%r", r.returncode, r.stdout, r.stderr)
    if r.returncode != 0 or not r.stdout.strip():
        notify("Uploaded, no link", r.stderr.strip() or "rclone link failed")
        return 1

    url = r.stdout.strip()

    try:
        subprocess.run(["wl-copy"], input=url, text=True, check=False)
    except FileNotFoundError:
        logging.warning("wl-copy not installed")

    subprocess.Popen(
        ["xdg-open", url],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    notify("Uploaded to Drive", "Share link copied · opening Drive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
