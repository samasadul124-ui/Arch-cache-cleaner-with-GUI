"""Provider list row: name, category, measured size, per-provider controls."""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from ..core.engine import ProviderScan  # noqa: E402
from ..core.safety import SafetyLevel  # noqa: E402
from ..core.units import format_bytes  # noqa: E402


class ProviderRow(Gtk.ListBoxRow):
    def __init__(self, scan: ProviderScan,
                 on_clean: Callable[[str], None],
                 interactive: bool = True) -> None:
        super().__init__()
        self.scan = scan
        p = scan.provider
        self.set_selectable(False)
        self.set_activatable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # ---- left: name + category
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)
        name = Gtk.Label(label=p.name)
        name.set_halign(Gtk.Align.START)
        name.add_css_class("heading")
        sub = Gtk.Label(label=f"{p.category.value}  ·  {p.id}"
                              + ("  ·  needs administrator" if scan.needs_elevation else ""))
        sub.set_halign(Gtk.Align.START)
        sub.add_css_class("caption")
        sub.add_css_class("cc-subtle")
        left.append(name)
        left.append(sub)
        if p.safety is SafetyLevel.CONDITIONAL_CACHE:
            tip = Gtk.Label(label="Conditional — requires explicit approval below")
            tip.set_halign(Gtk.Align.START)
            tip.add_css_class("caption")
            left.append(tip)
        box.append(left)

        # ---- right: size + controls
        size = Gtk.Label(label=format_bytes(scan.size_bytes))
        size.add_css_class("dim-label")
        box.append(size)

        self.approve: Optional[Gtk.CheckButton] = None
        if p.safety is SafetyLevel.CONDITIONAL_CACHE and interactive:
            self.approve = Gtk.CheckButton(label="Include")
            self.approve.set_tooltip_text(p.explain())
            box.append(self.approve)

        if interactive:
            btn = Gtk.Button(label="Clean")
            btn.set_tooltip_text(p.explain())
            btn.set_sensitive(not scan.needs_elevation and scan.size_bytes > 0)
            if scan.needs_elevation:
                btn.set_tooltip_text(
                    "Needs administrator privileges — use the pacman helper "
                    "or run: sudo paccache -r")
            btn.connect("clicked", lambda _b: on_clean(p.id))
            box.append(btn)

        self.set_child(box)

    @property
    def approved(self) -> bool:
        return bool(self.approve and self.approve.get_active())
