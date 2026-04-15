#!/usr/bin/env python3
"""Floating HUD shown while a recording is in progress.

Polls the PID file; closes itself when the recorder is gone. The Stop button
delegates to `cosmic-capture`, which detects the live PID and stops cleanly
(same path Print Screen takes to toggle).
"""
import os
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


def recorder_alive() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE) as f:
            pid = int(f.readline().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class HUD(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Recording")
        self.set_default_size(220, 72)
        self.set_resizable(False)
        self.set_decorated(False)

        self.started = time.monotonic()

        header = Adw.HeaderBar()
        header.set_show_title(False)
        header.set_visible(False)

        dot = Gtk.Label(label="\u25CF")
        dot.add_css_class("error")
        dot.add_css_class("title-1")

        self.timer = Gtk.Label(label="00:00")
        self.timer.add_css_class("title-3")

        stop = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
        stop.set_tooltip_text("Stop recording")
        stop.add_css_class("destructive-action")
        stop.add_css_class("circular")
        stop.connect("clicked", self._on_stop)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(10)
        row.set_margin_bottom(10)
        row.set_margin_start(16)
        row.set_margin_end(12)
        row.append(dot)
        row.append(self.timer)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.append(spacer)
        row.append(stop)

        self.set_content(row)
        GLib.timeout_add_seconds(1, self._tick)

    def _tick(self) -> bool:
        if not recorder_alive():
            self.close()
            return False
        elapsed = int(time.monotonic() - self.started)
        m, s = divmod(elapsed, 60)
        self.timer.set_label(f"{m:02d}:{s:02d}")
        return True

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
