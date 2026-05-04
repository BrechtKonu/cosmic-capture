#!/usr/bin/env python3
import logging
import os
import subprocess
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk, Gdk  # noqa: E402

LOG_PATH = "/tmp/cosmic-capture-overlay.log"
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(process)d %(message)s",
)

HELPER_DIR = os.path.dirname(os.path.realpath(__file__))


SCRIPTS = {
    "screenshot": "screenshot.py",
    "annotate":   "annotate.py",
    "record":     "record.py",
}


def launch(mode: str, win: Gtk.Window) -> None:
    logging.info("launch mode=%s", mode)
    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, SCRIPTS[mode])],
        env={**os.environ},
        start_new_session=True,
    )
    win.close()


class CaptureWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Capture")
        self.set_default_size(480, 180)
        self.set_resizable(False)

        header = Adw.HeaderBar()
        header.set_show_title(False)

        shot = Gtk.Button(label="Screenshot")
        shot.add_css_class("suggested-action")
        shot.add_css_class("pill")
        shot.set_hexpand(True)
        shot.set_tooltip_text("S or 1 — capture region to clipboard + folder")
        shot.connect("clicked", lambda _b: launch("screenshot", self))

        ann = Gtk.Button(label="Annotate")
        ann.add_css_class("pill")
        ann.set_hexpand(True)
        ann.set_tooltip_text("A or 2 — capture, then annotate in Satty")
        ann.connect("clicked", lambda _b: launch("annotate", self))

        rec = Gtk.Button(label="Record")
        rec.add_css_class("destructive-action")
        rec.add_css_class("pill")
        rec.set_hexpand(True)
        rec.set_tooltip_text("R or 3 — start screen recording")
        rec.connect("clicked", lambda _b: launch("record", self))

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons.set_margin_top(16)
        buttons.set_margin_bottom(20)
        buttons.set_margin_start(20)
        buttons.set_margin_end(20)
        buttons.append(shot)
        buttons.append(ann)
        buttons.append(rec)

        hint = Gtk.Label(label="S / A / R  or  1 / 2 / 3  ·  Esc to cancel  ·  Print Screen again to stop recording")
        hint.add_css_class("dim-label")
        hint.set_margin_bottom(12)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(header)
        root.append(buttons)
        root.append(hint)
        self.set_content(root)

        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", self._on_key)
        self.add_controller(esc)

    _KEYMAP = {
        Gdk.KEY_1: "screenshot",
        Gdk.KEY_2: "annotate",
        Gdk.KEY_3: "record",
        Gdk.KEY_s: "screenshot", Gdk.KEY_S: "screenshot",
        Gdk.KEY_a: "annotate",   Gdk.KEY_A: "annotate",
        Gdk.KEY_r: "record",     Gdk.KEY_R: "record",
    }

    def _on_key(self, _ctrl, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        mode = self._KEYMAP.get(keyval)
        if mode:
            launch(mode, self)
            return True
        return False


class CaptureApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="dev.brecht.CosmicCapture",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )

    def do_activate(self) -> None:  # type: ignore[override]
        logging.info("app activate is_remote=%s", self.get_is_remote())
        win = CaptureWindow(self)
        win.present()


if __name__ == "__main__":
    sys.exit(CaptureApp().run(sys.argv))
