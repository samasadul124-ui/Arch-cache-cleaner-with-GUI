"""GTK4 + libadwaita GUI layer.

GTK/GLib are imported ONLY inside this subpackage so the engine and CLI stay
usable on headless systems. Entry: ``cachecleaner.gui.app.run_app()``.
"""
