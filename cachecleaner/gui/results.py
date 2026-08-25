"""Cleanup report panel: before / removed / remaining + counts + errors."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..core.engine import CleanReport  # noqa: E402
from ..core.units import format_bytes  # noqa: E402


def _stat(label: str, value: str, css: str = "") -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    v = Gtk.Label(label=value)
    v.add_css_class("cc-stat-value")
    if css:
        v.add_css_class(css)
    l = Gtk.Label(label=label)
    l.add_css_class("caption")
    l.add_css_class("cc-subtle")
    box.append(v)
    box.append(l)
    return box


def build_report_panel(report: CleanReport) -> Gtk.Box:
    """The full after-cleanup summary required by rule 1/6."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
    grid.set_halign(Gtk.Align.CENTER)
    grid.append(_stat("Before", format_bytes(report.before_bytes)))
    grid.append(_stat("Removed", format_bytes(report.removed_bytes), "accent"))
    remaining = (report.after_bytes
                 if report.after_bytes is not None else report.removed_bytes)
    grid.append(_stat("Remaining (fresh scan)", format_bytes(remaining)))
    grid.append(_stat("Cleaned", str(len(report.cleaned))))
    grid.append(_stat("Skipped", str(len(report.skipped))))
    grid.append(_stat("Errors", str(len(report.failed)),
                      "cc-error-row" if report.failed else ""))
    outer.append(grid)

    if report.cancelled:
        note = Gtk.Label(label="Cleanup was cancelled — the numbers above "
                               "reflect the work completed before cancellation.")
        note.add_css_class("caption")
        outer.append(note)

    if report.errors.records:
        exp = Gtk.Expander(label=f"Error details ({len(report.errors.records)})")
        listBox = Gtk.ListBox()
        listBox.set_selection_mode(Gtk.SelectionMode.NONE)
        listBox.add_css_class("boxed-list")
        for rec in report.errors.records[:50]:
            row = Gtk.Label(label=f"[{rec.kind.value}] {rec.path} — {rec.detail}")
            row.set_wrap(True)
            row.set_xalign(0)
            row.add_css_class("caption")
            row.add_css_class("cc-error-row")
            listBox.append(row)
        scroll = Gtk.ScrolledWindow()
        scroll.set_max_content_height(180)
        scroll.set_propagate_natural_height(True)
        scroll.set_child(listBox)
        exp.set_child(scroll)
        outer.append(exp)

    return outer
