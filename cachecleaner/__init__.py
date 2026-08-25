"""Cache Cleaner — safe cache discovery & cleanup for EndeavourOS / Arch Linux.

Package root. Deliberately free of GTK/GLib imports so that the core engine,
providers and CLI can be imported and tested on headless systems.
"""

from __future__ import annotations

__version__ = "0.1.1"
APP_ID = "io.github.cachecleaner.App"
APP_NAME = "Cache Cleaner"

__all__ = ["__version__", "APP_ID", "APP_NAME"]
