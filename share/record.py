#!/usr/bin/env python3
"""Start or stop a gpu-screen-recorder region session.

On start: slurp to pick a region, spawn gpu-screen-recorder against it,
and launch the floating HUD (Stop button).
On stop: send SIGINT to the recorder's process group so the file is finalized.

Scaled-monitor workaround
-------------------------
gpu-screen-recorder 5.12's `-w <region>` mode silently downscales the
captured stream by the inverse of the monitor's fractional scale factor
(e.g. on a 150% monitor a 800x600 selection produces a 200x150 video).
On unscaled monitors the same code path is correct.

To work around this without losing region selection, when the picked
region lands on a scaled monitor we capture the *full* monitor (which
records at correct physical resolution) and crop to the requested
region with ffmpeg after the recorder exits. The crop coordinates are
stashed in the PID file and consumed by stop().
"""
import datetime as _dt
import logging
import os
import re
import signal
import subprocess
import sys
import time

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


def read_state() -> tuple[int, str, str] | None:
    """Returns (pid, output_path, crop_spec) or None.

    crop_spec is "" (no crop needed) or "WxH+X+Y" in physical pixel coords.
    """
    if not os.path.exists(PID_FILE):
        return None
    with open(PID_FILE) as f:
        lines = f.read().splitlines()
    if len(lines) < 2:
        return None
    try:
        pid = int(lines[0].strip())
    except ValueError:
        return None
    path = lines[1].strip()
    crop = lines[2].strip() if len(lines) >= 3 else ""
    try:
        os.kill(pid, 0)
    except OSError:
        try:
            os.unlink(PID_FILE)
        except OSError:
            pass
        return None
    return pid, path, crop


def wait_for_file_stable(path: str, timeout: float = 30.0,
                         stable_for: float = 1.0) -> bool:
    """Wait until `path` exists and its size has been unchanged for `stable_for`
    seconds. Used to detect that gpu-screen-recorder has finished muxing —
    more reliable than waiting on the flatpak/bwrap wrapper PID, which can
    outlive the actual recorder.
    """
    deadline = time.monotonic() + timeout
    last_size = -1
    last_change = time.monotonic()
    while time.monotonic() < deadline:
        try:
            sz = os.path.getsize(path)
        except OSError:
            sz = -1
        if sz != last_size:
            last_size = sz
            last_change = time.monotonic()
        elif sz > 0 and time.monotonic() - last_change >= stable_for:
            return True
        time.sleep(0.2)
    logging.warning("file %s not stable after %.1fs", path, timeout)
    return False


def crop_in_place(path: str, crop_spec: str) -> bool:
    """Crop `path` to `crop_spec` (WxH+X+Y) using ffmpeg, replacing the file.

    Tries host ffmpeg (apt-installed) first, since the gpu-screen-recorder
    flatpak's bundled ffmpeg has the h264 decoder stripped out. Returns True
    on success.
    """
    m = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", crop_spec)
    if not m:
        logging.error("invalid crop_spec: %r", crop_spec)
        return False
    w, h, x, y = (int(v) for v in m.groups())
    # h264 needs even dimensions; round down to even.
    w -= w % 2
    h -= h % 2
    tmp = path + ".crop.mp4"

    import shutil
    if not shutil.which("ffmpeg"):
        logging.error("ffmpeg not found on host; install with: sudo apt install ffmpeg")
        notify("Crop skipped", "Install ffmpeg: sudo apt install ffmpeg")
        return False

    # Prefer NVENC if available; fall back to libx264.
    encoders = ["h264_nvenc", "libx264"]
    for enc in encoders:
        if enc == "h264_nvenc":
            enc_args = ["-c:v", enc, "-preset", "p4", "-cq", "20"]
        else:
            enc_args = ["-c:v", enc, "-preset", "ultrafast", "-crf", "20"]
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-vf", f"crop={w}:{h}:{x}:{y}",
            *enc_args,
            "-c:a", "copy",
            tmp,
        ]
        logging.info("cropping (%s): %s", enc, " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            os.replace(tmp, path)
            return True
        logging.warning("ffmpeg %s failed rc=%s; %s", enc, r.returncode, r.stderr[-300:])
        try: os.unlink(tmp)
        except OSError: pass
    return False


def stop(pid: int, path: str, crop_spec: str) -> int:
    try:
        os.killpg(os.getpgid(pid), signal.SIGINT)
    except OSError as e:
        notify("Stop failed", str(e))
        return 1
    try:
        os.unlink(PID_FILE)
    except OSError:
        pass

    if crop_spec:
        notify("Recording stopped", "Cropping…")
        wait_for_file_stable(path)
        if not crop_in_place(path, crop_spec):
            notify("Crop failed", "Keeping uncropped recording")

    notify("Recording stopped", path)

    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, "sync_and_share.py"),
         "recording", path, str(pid)],
        start_new_session=True,
    )
    return 0


def get_monitor_scales() -> dict[str, float]:
    """Parse `cosmic-randr list` output for {monitor_name: scale_factor}.

    Returns {} if cosmic-randr is unavailable. Anything we can't parse
    defaults to 1.0 at the call site.
    """
    try:
        r = subprocess.run(
            ["cosmic-randr", "list"],
            capture_output=True, text=True, env={**os.environ, "NO_COLOR": "1"},
        )
    except FileNotFoundError:
        return {}
    if r.returncode != 0:
        return {}
    # Strip ANSI escape sequences (cosmic-randr ignores NO_COLOR).
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", r.stdout)
    scales: dict[str, float] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z]+-\d+)\s", line)
        if m:
            current = m.group(1)
            continue
        if current is None:
            continue
        m = re.match(r"\s*Scale:\s*(\d+)%", line)
        if m:
            scales[current] = int(m.group(1)) / 100.0
    return scales


def pick_region() -> tuple[str, int, int, int, int] | None:
    """Pick a region with slurp.

    Returns (monitor_name, x_rel, y_rel, w, h) where coords are *logical*
    pixels relative to the picked monitor, or None on cancel.
    """
    try:
        r = subprocess.run(
            ["slurp", "-f", "%o %X %Y %W %H"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        notify("Record failed", "slurp not installed (sudo apt install slurp)")
        return None
    if r.returncode != 0:
        return None
    parts = r.stdout.split()
    if len(parts) != 5 or parts[0] == "<unknown>":
        logging.warning("slurp returned unparseable output: %r", r.stdout)
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
    except ValueError:
        return None


def start() -> int:
    save_dir = cfg("record_dir") or os.path.expanduser("~/Videos")
    template = cfg("filename_template", "%Y-%m-%d_%H-%M-%S")
    backend = cfg("recorder_backend", "gpu-screen-recorder-flatpak")
    codec = cfg("recorder_codec", "h264")
    fps = cfg("recorder_fps", "60")
    audio = cfg("recorder_audio", "default_output")

    picked = pick_region()
    if picked is None:
        return 0  # cancelled
    monitor, x_rel, y_rel, w, h = picked

    scales = get_monitor_scales()
    scale = scales.get(monitor, 1.0)
    logging.info("picked monitor=%s region=%dx%d+%d+%d (relative) scale=%g",
                 monitor, w, h, x_rel, y_rel, scale)

    os.makedirs(save_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime(template)
    out_path = os.path.join(save_dir, f"{stamp}.mp4")

    if scale == 1.0:
        # Native region capture works correctly on unscaled monitors. We need
        # global (virtual-desktop) coordinates here — slurp's %X/%Y are
        # monitor-relative, so add the monitor's logical origin. cosmic-randr
        # gives us "Position: X,Y" but for scale=1 monitors %x/%y == %X+origin,
        # so just re-run slurp's geometry would be cleaner — instead we use
        # the simpler global form by re-asking slurp wouldn't make sense here;
        # we already have the region, and on unscaled monitors gpu-screen-recorder
        # accepts logical absolute coords. Look the origin up from cosmic-randr.
        origin = get_monitor_origin(monitor)
        gx = x_rel + origin[0]
        gy = y_rel + origin[1]
        target = "-w"
        target_arg = f"{w}x{h}+{gx}+{gy}"
        crop_spec = ""
        gsr_args = [target, target_arg]
    else:
        # Capture full monitor; crop afterwards. Physical = logical * scale.
        crop_w = round(w * scale)
        crop_h = round(h * scale)
        crop_x = round(x_rel * scale)
        crop_y = round(y_rel * scale)
        crop_spec = f"{crop_w}x{crop_h}+{crop_x}+{crop_y}"
        gsr_args = ["-w", monitor]
        logging.info("scaled monitor: capturing full %s, crop=%s", monitor, crop_spec)

    args = [
        *gsr_args,
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
        f.write(f"{proc.pid}\n{out_path}\n{crop_spec}\n")

    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, "recorder_hud.py")],
        env={**os.environ},
        start_new_session=True,
    )

    notify("Recording started", f"→ {out_path}")
    return 0


def get_monitor_origin(name: str) -> tuple[int, int]:
    """Find a monitor's logical-pixel origin via `cosmic-randr list`.

    Falls back to (0, 0) if not found.
    """
    try:
        r = subprocess.run(["cosmic-randr", "list"], capture_output=True, text=True)
    except FileNotFoundError:
        return (0, 0)
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", r.stdout)
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z]+-\d+)\s", line)
        if m:
            current = m.group(1)
            continue
        if current != name:
            continue
        m = re.match(r"\s*Position:\s*(\d+),(\d+)", line)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    return (0, 0)


def main() -> int:
    existing = read_state()
    if existing:
        return stop(*existing)
    return start()


if __name__ == "__main__":
    sys.exit(main())
