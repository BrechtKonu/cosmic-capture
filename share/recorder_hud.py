#!/usr/bin/env python3
"""Floating HUD shown while a recording is in progress.

Polls the PID file; closes itself when the recorder exits. The Stop button
delegates to `cosmic-capture`, which detects the live PID and stops cleanly
(same path Print Screen takes to toggle). The Pause button sends SIGUSR2 to
the recorder process group, which gpu-screen-recorder treats as a
pause/resume toggle.
"""
import os
import signal
import subprocess
import sys
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

PID_FILE = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
    "cosmic-capture.pid",
)


def read_pid_and_path() -> tuple[int, str] | None:
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            raw = f.read()
    except OSError:
        return None
    pid_s, _, path = raw.partition("\n")
    try:
        pid = int(pid_s.strip())
    except ValueError:
        return None
    return pid, path.strip()


def recorder_alive() -> bool:
    info = read_pid_and_path()
    if info is None:
        return False
    try:
        os.kill(info[0], 0)
        return True
    except OSError:
        return False


def fmt_size(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


class HUD(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Recording")
        self.set_default_size(280, 64)
        self.set_resizable(False)
        self.set_decorated(False)

        self.started = time.monotonic()
        self.paused = False
        self.pause_started: float | None = None
        self.pause_total = 0.0

        self.dot = Gtk.Label(label="●")
        self.dot.add_css_class("error")
        self.dot.add_css_class("title-1")

        self.timer = Gtk.Label(label="00:00")
        self.timer.add_css_class("title-3")

        self.size_label = Gtk.Label(label="")
        self.size_label.add_css_class("dim-label")
        self.size_label.add_css_class("caption")

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_col.append(self.timer)
        text_col.append(self.size_label)

        self.pause_btn = Gtk.Button.new_from_icon_name("media-playback-pause-symbolic")
        self.pause_btn.set_tooltip_text("Pause / resume")
        self.pause_btn.add_css_class("circular")
        self.pause_btn.connect("clicked", self._on_pause)

        stop = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
        stop.set_tooltip_text("Stop recording")
        stop.add_css_class("destructive-action")
        stop.add_css_class("circular")
        stop.connect("clicked", self._on_stop)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_top(8)
        row.set_margin_bottom(8)
        row.set_margin_start(14)
        row.set_margin_end(12)
        row.append(self.dot)
        row.append(text_col)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.append(spacer)
        row.append(self.pause_btn)
        row.append(stop)

        self.set_content(row)
        GLib.timeout_add_seconds(1, self._tick)

    def _tick(self) -> bool:
        info = read_pid_and_path()
        if info is None or not self._alive(info[0]):
            self.close()
            return False

        path = info[1]
        if path and os.path.exists(path):
            try:
                self.size_label.set_label(fmt_size(os.path.getsize(path)))
            except OSError:
                pass

        if self.paused:
            return True

        elapsed = int(time.monotonic() - self.started - self.pause_total)
        m, s = divmod(elapsed, 60)
        self.timer.set_label(f"{m:02d}:{s:02d}")
        return True

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _on_pause(self, _btn: Gtk.Button) -> None:
        info = read_pid_and_path()
        if info is None:
            return
        pid = info[0]
        try:
            os.killpg(os.getpgid(pid), signal.SIGUSR2)
        except OSError:
            return

        self.paused = not self.paused
        if self.paused:
            self.pause_started = time.monotonic()
            self.pause_btn.set_icon_name("media-playback-start-symbolic")
            self.pause_btn.set_tooltip_text("Resume recording")
            self.dot.remove_css_class("error")
            self.dot.add_css_class("warning")
        else:
            if self.pause_started is not None:
                self.pause_total += time.monotonic() - self.pause_started
                self.pause_started = None
            self.pause_btn.set_icon_name("media-playback-pause-symbolic")
            self.pause_btn.set_tooltip_text("Pause recording")
            self.dot.remove_css_class("warning")
            self.dot.add_css_class("error")

    def _on_stop(self, _btn: Gtk.Button) -> None:
        subprocess.Popen(
            [os.path.expanduser("~/.local/bin/cosmic-capture")],
            env={**os.environ},
            start_new_session=True,
        )


class HUDApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="dev.brecht.CosmicCaptureHUD")

    def do_activate(self) -> None:  # type: ignore[override]
        HUD(self).present()


if __name__ == "__main__":
    if not recorder_alive():
        sys.exit(0)
    sys.exit(HUDApp().run(sys.argv))
