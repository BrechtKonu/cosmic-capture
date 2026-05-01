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

MODE_CHOICES = ("region", "full")
DELAY_CHOICES = (0, 3, 5)


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(f"COSMIC_CAPTURE_{key.upper()}", default)


def cfg_bool(key: str, default: bool = False) -> bool:
    v = cfg(key, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def launch(mode: str, win: Gtk.Window, extra_args: list[str]) -> None:
    logging.info("launch mode=%s args=%s", mode, extra_args)
    script = "screenshot.py" if mode == "screenshot" else "record.py"
    subprocess.Popen(
        [sys.executable, os.path.join(HELPER_DIR, script), *extra_args],
        env={**os.environ},
        start_new_session=True,
    )
    win.close()


class CaptureWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Capture")
        self.set_default_size(420, 240)
        self.set_resizable(False)

        header = Adw.HeaderBar()
        header.set_show_title(False)

        # Primary actions ----------------------------------------------------
        shot = Gtk.Button(label="Screenshot")
        shot.add_css_class("suggested-action")
        shot.add_css_class("pill")
        shot.set_hexpand(True)
        shot.connect("clicked", lambda _b: launch("screenshot", self, self._screenshot_args()))

        rec = Gtk.Button(label="Record")
        rec.add_css_class("destructive-action")
        rec.add_css_class("pill")
        rec.set_hexpand(True)
        rec.connect("clicked", lambda _b: launch("record", self, self._record_args()))

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons.set_margin_top(16)
        buttons.set_margin_start(20)
        buttons.set_margin_end(20)
        buttons.append(shot)
        buttons.append(rec)

        # Options row --------------------------------------------------------
        default_mode = cfg("default_mode", "region")
        default_delay = int(cfg("default_delay", "0") or "0")
        default_annotate = cfg_bool("annotate_default", False)

        self.mode_drop = Gtk.DropDown.new_from_strings(["Region", "Full"])
        self.mode_drop.set_selected(MODE_CHOICES.index(default_mode) if default_mode in MODE_CHOICES else 0)

        self.delay_drop = Gtk.DropDown.new_from_strings(["0s", "3s", "5s"])
        self.delay_drop.set_selected(
            DELAY_CHOICES.index(default_delay) if default_delay in DELAY_CHOICES else 0
        )

        self.annotate_check = Gtk.CheckButton(label="Annotate")
        self.annotate_check.set_active(default_annotate)
        self.annotate_check.set_tooltip_text(
            "Open satty after capture for drawing/highlighting"
        )

        def labelled(text: str, widget: Gtk.Widget) -> Gtk.Box:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl = Gtk.Label(label=text, xalign=0)
            lbl.add_css_class("dim-label")
            lbl.add_css_class("caption")
            box.append(lbl)
            box.append(widget)
            return box

        options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        options.set_margin_top(14)
        options.set_margin_start(20)
        options.set_margin_end(20)
        options.set_halign(Gtk.Align.CENTER)
        options.append(labelled("Mode", self.mode_drop))
        options.append(labelled("Delay", self.delay_drop))

        annotate_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        annotate_wrap.set_valign(Gtk.Align.END)
        annotate_wrap.append(self.annotate_check)
        options.append(annotate_wrap)

        # Hint ---------------------------------------------------------------
        hint = Gtk.Label(label="Esc to cancel  ·  Print Screen again to stop recording")
        hint.add_css_class("dim-label")
        hint.set_margin_top(14)
        hint.set_margin_bottom(12)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(header)
        root.append(buttons)
        root.append(options)
        root.append(hint)
        self.set_content(root)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    # ----------------------------------------------------------------- args
    def _screenshot_args(self) -> list[str]:
        args: list[str] = ["--mode", MODE_CHOICES[self.mode_drop.get_selected()]]
        delay = DELAY_CHOICES[self.delay_drop.get_selected()]
        if delay > 0:
            args += ["--delay", str(delay)]
        if self.annotate_check.get_active():
            args.append("--annotate")
        return args

    def _record_args(self) -> list[str]:
        # Region maps 1:1; "Full" → "screen" for the recorder (portal).
        sel = MODE_CHOICES[self.mode_drop.get_selected()]
        rec_mode = "region" if sel == "region" else "screen"
        return ["--mode", rec_mode]

    # -------------------------------------------------------------- shortcuts
    def _on_key(self, _ctrl, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval == Gdk.KEY_1:
            launch("screenshot", self, self._screenshot_args())
            return True
        if keyval == Gdk.KEY_2:
            launch("record", self, self._record_args())
            return True
        if keyval == Gdk.KEY_a:
            self.annotate_check.set_active(not self.annotate_check.get_active())
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
