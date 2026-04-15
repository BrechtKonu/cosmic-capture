#!/usr/bin/env python3
"""Start or stop a gpu-screen-recorder region session.

On start: slurp to pick a region, spawn gpu-screen-recorder against it,
and launch the floating HUD (Stop button).
On stop: send SIGINT to the recorder's process group so the file is finalized.
"""
import datetime as _dt
import logging
import os
import signal
import subprocess
import sys

LOG_PATH = "/tmp/cosmic-capture-record.log"
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

HELPER_DIR = os.path.dirname(os.path.realpath(__file__))
PID_FILE = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
    "cosmic-capture.pid",
)


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(f"COSMIC_CAPTURE_{key.upper()}", default)


def notify(summary: str, body: str = "", open_path: str | None = None) -> None:
    subprocess.Popen(
        ["notify-send", "-a", "Cosmic Capture", summary, body],
        start_new_session=True,
    )


def read_state() -> tuple[int, str] | None:
    if not os.path.exists(PID_FILE):
        return None
    with open(PID_FILE) as f:
        raw = f.read()
    pid_s, _, path = raw.partition("\n")
    try:
        pid = int(pid_s.strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        try:
            os.unlink(PID_FILE)
        except OSError:
            pass
        return None
    return pid, path.strip()


def stop(pid: int, path: str) -> int:
    try:
        os.killpg(os.getpgid(pid), signal.SIGINT)
    except OSError as e:
        notify("Stop failed", str(e))
        return 1
    try:
        os.unlink(PID_FILE)
    except OSError:
        pass
    notify("Recording stopped", path)

    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, "sync_and_share.py"),
         "recording", path, str(pid)],
        start_new_session=True,
    )
    return 0


def pick_region() -> str | None:
    try:
        r = subprocess.run(
            ["slurp", "-f", "%wx%h+%x+%y"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        notify("Record failed", "slurp not installed (sudo apt install slurp)")
        return None
    if r.returncode != 0:
        return None
    geom = r.stdout.strip()
    return geom or None


def start() -> int:
    save_dir = cfg("record_dir") or os.path.expanduser("~/Videos")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
    backend = cfg("recorder_backend", "gpu-screen-recorder-flatpak")
    codec = cfg("recorder_codec", "h264")
    fps = cfg("recorder_fps", "60")
    audio = cfg("recorder_audio", "default_output")

    region = pick_region()
    if region is None:
        return 0  # cancelled

    os.makedirs(save_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime(template)
    out_path = os.path.join(save_dir, f"{stamp}.mp4")

    args = [
        "-w", "region",
        "-region", region,
        "-c", "mp4",
        "-k", codec,
        "-f", fps,
        "-o", out_path,
    ]
    if audio and audio != "none":
        args.extend(["-a", audio])

    if backend == "gpu-screen-recorder-flatpak":
        cmd = ["flatpak", "run", "--command=gpu-screen-recorder",
               "com.dec05eba.gpu_screen_recorder", *args]
    else:
        cmd = ["gpu-screen-recorder", *args]

    try:
        proc = subprocess.Popen(cmd, start_new_session=True)
    except FileNotFoundError as e:
        notify("Recorder not installed", str(e))
        return 1

    with open(PID_FILE, "w") as f:
        f.write(f"{proc.pid}\n{out_path}")

    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, "recorder_hud.py")],
        env={**os.environ},
        start_new_session=True,
    )

    notify("Recording started", f"\u2192 {out_path}")
    return 0


def main() -> int:
    existing = read_state()
    if existing:
        return stop(*existing)
    return start()


if __name__ == "__main__":
    sys.exit(main())
