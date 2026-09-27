"""
PipeSync Libadwaita Application Entry Point
"""

import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from pipesync.constants import APP_ID, APP_NAME
from pipesync.gui.main_window import MainWindow


class PipeSyncApp(Adw.Application):
    """PipeSync GTK4 / Libadwaita Application."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self)
        self.window.present()


def main():
    app = PipeSyncApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
