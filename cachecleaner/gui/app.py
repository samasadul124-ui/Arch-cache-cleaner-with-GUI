"""Application object: Adw.Application, CSS theme, window lifecycle."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from .. import APP_ID, APP_NAME, __version__  # noqa: E402
from ..core import log  # noqa: E402

_logger = log.get_logger("gui.app")

_CSS = b"""
.cc-total-label { font-size: 44px; font-weight: 800; }
.cc-subtle { color: alpha(currentColor, .65); }
.cc-stat-value { font-size: 20px; font-weight: 700; }
.cc-error-row { color: #e01b24; }
"""


class CacheCleanerApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.set_application_name(APP_NAME)
        self.set_version(__version__)
        self.window = None

    def do_activate(self) -> None:  # noqa: N802 (GObject vfunc)
        if not self.window:
            from .window import MainWindow
            css = Gtk.CssProvider()
            css.load_from_data(_CSS)
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.window = MainWindow(self)
            log.log_event(_logger, "window_created")
        self.window.present()


def run_app() -> int:
    log.setup_logging()
    app = CacheCleanerApp()
    return app.run(None)
