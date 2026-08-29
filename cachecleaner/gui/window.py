"""Main window: dashboard, provider list, clean-all flow, results (rules 1, 11)."""

from __future__ import annotations

import os
import threading
from enum import Enum, auto
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import APP_NAME, __version__  # noqa: E402
from ..core import log  # noqa: E402
from ..core.engine import CleanReport, Engine, ScanReport  # noqa: E402
from ..core.safety import SafetyLevel  # noqa: E402
from ..core.units import format_bytes  # noqa: E402
from .provider_row import ProviderRow  # noqa: E402
from .results import build_report_panel  # noqa: E402

_logger = log.get_logger("gui.window")


class State(Enum):
    SCANNING = auto()
    READY = auto()
    CLEANING = auto()
    FINISHED = auto()
    PARTIAL = auto()
    FATAL = auto()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=APP_NAME,
                         default_width=800, default_height=720)
        self.engine = Engine()
        self.report: Optional[ScanReport] = None
        self.cancel_event = threading.Event()
        self._busy = False

        # ----------------------------------------------------------- header
        header = Gtk.HeaderBar()
        self.rescan_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.rescan_btn.set_tooltip_text("Rescan")
        self.rescan_btn.connect("clicked", lambda _b: self.start_scan())
        header.pack_start(self.rescan_btn)

        menu = Gio.Menu()
        menu.append("About Cache Cleaner", "win.about")
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self._show_about)
        self.add_action(about)
        self._toolbar_view = Adw.ToolbarView()
        self._toolbar_view.add_top_bar(header)

        # ---------------------------------------------------------- content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)

        # dashboard card ----------------------------------------------------
        dash = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dash.add_css_class("card")
        dash.set_margin_top(6)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_margin_top(24)
        inner.set_margin_bottom(24)
        inner.set_margin_start(24)
        inner.set_margin_end(24)

        self.state_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.state_row.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        self.state_label = Gtk.Label(label="Starting…")
        self.state_label.add_css_class("caption")
        self.state_row.append(self.spinner)
        self.state_row.append(self.state_label)
        inner.append(self.state_row)

        self.total_label = Gtk.Label(label="—")
        self.total_label.add_css_class("cc-total-label")
        inner.append(self.total_label)

        self.sub_label = Gtk.Label(label="total detected cache")
        self.sub_label.add_css_class("cc-subtle")
        inner.append(self.sub_label)

        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        self.progress.set_margin_top(10)
        inner.append(self.progress)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(14)
        self.clean_btn = Gtk.Button(label="Clean All Cache")
        self.clean_btn.add_css_class("destructive-action")
        self.clean_btn.add_css_class("pill")
        self.clean_btn.set_sensitive(False)
        self.clean_btn.connect("clicked", lambda _b: self.clean_all())
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.set_visible(False)
        self.cancel_btn.connect("clicked", lambda _b: self.cancel_event.set())
        actions.append(self.clean_btn)
        actions.append(self.cancel_btn)
        inner.append(actions)

        dash.append(inner)
        content.append(dash)

        # results holder ------------------------------------------------------
        self.results_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.results_holder.add_css_class("card")
        self.results_holder.set_visible(False)
        self.results_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.results_inner.set_margin_top(18)
        self.results_inner.set_margin_bottom(18)
        self.results_inner.set_margin_start(18)
        self.results_inner.set_margin_end(18)
        title = Gtk.Label(label="Cleanup results")
        title.add_css_class("heading")
        self.results_inner.append(title)
        self.results_holder.append(self.results_inner)
        content.append(self.results_holder)

        # providers card -------------------------------------------------------
        prov_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prov_head = Gtk.Label(label="Detected cache providers")
        prov_head.add_css_class("heading")
        prov_head.set_halign(Gtk.Align.START)
        prov_card.append(prov_head)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        placeholder = Gtk.Label(label="No scan yet — press Rescan.")
        placeholder.set_margin_top(18)
        placeholder.set_margin_bottom(18)
        self.list.set_placeholder(placeholder)
        prov_card.append(self.list)
        content.append(prov_card)

        # advanced sweep (layer 5, manual selection only) ----------------
        adv_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        adv_head.set_margin_top(6)
        adv_lbl = Gtk.Label(
            label="Advanced: show every folder named '*cache*' "
                  "(you select each one yourself)")
        adv_lbl.set_halign(Gtk.Align.START)
        adv_lbl.add_css_class("caption")
        self.adv_switch = Gtk.Switch()
        self.adv_switch.set_valign(Gtk.Align.CENTER)
        self.adv_switch.connect("state-set", self._on_advanced_toggled)
        adv_head.append(adv_lbl)
        adv_head.append(self.adv_switch)
        content.append(adv_head)
        self.adv_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.adv_holder.set_visible(False)
        content.append(self.adv_holder)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(content)
        self._toolbar_view.set_content(scrolled)
        self.set_content(self._toolbar_view)

        log.log_event(_logger, "window_ready")
        self.start_scan()

    # ------------------------------------------------------------ state UI
    def _set_state(self, state: State) -> None:
        self.state_label.set_text({
            State.SCANNING: "Scanning filesystem…",
            State.READY: "Ready",
            State.CLEANING: "Cleaning…",
            State.FINISHED: "Cleanup finished",
            State.PARTIAL: "Cleanup finished with errors",
            State.FATAL: "Fatal error — see log",
        }[state])
        self.spinner.set_visible(state in (State.SCANNING, State.CLEANING))
        if self.spinner.get_visible():
            self.spinner.start()
        else:
            self.spinner.stop()
        self.progress.set_visible(state in (State.SCANNING, State.CLEANING))
        self.cancel_btn.set_visible(state == State.CLEANING)
        self.rescan_btn.set_sensitive(state in (State.READY, State.FINISHED,
                                               State.PARTIAL, State.FATAL))

    def _progress(self, frac: float, msg: str) -> bool:
        self.progress.set_fraction(min(1.0, max(0.0, frac)))
        if msg:
            self.state_label.set_text(msg)
        return False

    # ------------------------------------------------------------- scanning
    def start_scan(self, advanced: Optional[bool] = None) -> None:
        if self._busy:
            return
        if advanced is None:
            advanced = getattr(self, "_advanced", False)
        self._advanced = bool(advanced)
        self._busy = True
        self.cancel_event.clear()
        self._set_state(State.SCANNING)
        self.total_label.set_label("—")
        self.sub_label.set_label("scanning…")
        self.results_holder.set_visible(False)
        while (row := self.list.get_row_at_index(0)) is not None:
            self.list.remove(row)
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            report = self.engine.scan(
                progress=lambda f, m: GLib.idle_add(self._progress, f, m),
                advanced=self._advanced)
            sizes: dict = {}
            sweep = report.by_id("advanced.cache-name-sweep")
            if sweep is not None:
                from ..core.fs import dir_size
                for cp in sweep.provider.cache_paths()[:200]:
                    try:
                        sizes[cp.path] = dir_size(cp.path).bytes
                    except OSError:
                        sizes[cp.path] = 0
            GLib.idle_add(self._on_scan_done, report, sizes)
        except Exception as exc:                       # noqa: BLE001
            log.log_event(_logger, "scan_fatal", error=str(exc), level=40)
            GLib.idle_add(self._on_scan_fatal, str(exc))

    def _on_scan_done(self, report: ScanReport, sizes: Optional[dict] = None) -> bool:
        self.report = report
        self._busy = False
        self._build_advanced_card(sizes or {})
        self.total_label.set_label(format_bytes(report.total_bytes))
        self.sub_label.set_label(
            f"total detected cache · {report.provider_count} providers")
        for s in report.scans:
            self.list.append(ProviderRow(s, self._clean_one))
        self.clean_btn.set_sensitive(report.total_bytes > 0)
        self._set_state(State.READY)
        return False

    def _on_scan_fatal(self, msg: str) -> bool:
        self._busy = False
        self.total_label.set_label("—")
        self.sub_label.set_label(msg)
        self._set_state(State.FATAL)
        return False

    # ------------------------------------------------------- advanced sweep
    def _on_advanced_toggled(self, _sw, state) -> bool:
        self.start_scan(advanced=bool(state))
        return True

    def _build_advanced_card(self, sizes: dict) -> None:
        child = self.adv_holder.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.adv_holder.remove(child)
            child = nxt
        sweep = (self.report.by_id("advanced.cache-name-sweep")
                 if self.report else None)
        if sweep is None:
            self.adv_holder.set_visible(False)
            return
        paths = [cp.path for cp in sweep.provider.cache_paths()]
        if not paths:
            self.adv_holder.set_visible(False)
            return
        self.adv_holder.set_visible(True)
        self._sweep_checks: list = []
        box = Gtk.ListBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        home = self.engine.home
        for pth in paths[:200]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_margin_top(4)
            row.set_margin_bottom(4)
            row.set_margin_start(8)
            row.set_margin_end(8)
            cb = Gtk.CheckButton()
            cb.set_tooltip_text(pth)
            lbl = Gtk.Label(label=f"{os.path.relpath(pth, home)}   "
                                  f"{format_bytes(sizes.get(pth, 0))}")
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("caption")
            row.append(cb)
            row.append(lbl)
            box.append(row)
            self._sweep_checks.append((cb, pth))
        if len(paths) > 200:
            more = Gtk.Label(label=f"…and {len(paths) - 200} more "
                                   "(use the CLI --advanced to list all)")
            more.add_css_class("caption")
            box.append(more)
        btn = Gtk.Button(label="Clean selected")
        btn.add_css_class("destructive-action")
        btn.connect("clicked", lambda _b: self._clean_selected_sweep(sweep))
        self.adv_holder.append(box)
        self.adv_holder.append(btn)

    def _clean_selected_sweep(self, sweep) -> None:
        selected = {pth for cb, pth in getattr(self, "_sweep_checks", [])
                    if cb.get_active()}
        if not selected:
            return
        sweep.provider.selected = selected
        self._start_clean({sweep.provider.id}, {sweep.provider.id})

    # -------------------------------------------------------------- cleaning
    def _approved_conditional(self) -> set[str]:
        ids = set()
        i = 0
        while (row := self.list.get_row_at_index(i)) is not None:
            i += 1
            if isinstance(row, ProviderRow) and row.approved:
                ids.add(row.scan.provider.id)
        return ids

    def _eligible_ids(self) -> set[str]:
        ids = set()
        i = 0
        while (row := self.list.get_row_at_index(i)) is not None:
            i += 1
            if not isinstance(row, ProviderRow):
                continue
            p = row.scan.provider
            if getattr(p, "manual_selection_only", False):
                continue
            if p.safety is SafetyLevel.SAFE_CACHE and not row.scan.needs_elevation:
                ids.add(p.id)
        return ids

    def clean_all(self) -> None:
        if not self.report:
            return
        eligible = self._eligible_ids()
        approved = self._approved_conditional()
        if not eligible and not approved:
            return
        size = sum(s.size_bytes for s in self.report.scans
                   if s.provider.id in eligible | approved)
        body = (f"This removes {format_bytes(size)} of regenerable cache data "
                f"from {len(eligible | approved)} providers.\n"
                "Documents, configurations, credentials and browser profiles "
                "are never touched.")
        if any(s.needs_elevation for s in self.report.scans
               if s.provider.id in approved):
            body += ("\n\nThe system authentication dialog will appear for the "
                     "root-owned pacman package cache.")
        # E-016: never let excluded approval-requiring data look like a silent
        # no-op — name it in the confirmation dialog
        excluded = [s for s in self.report.scans
                    if s.conditional_bytes > 0 and s.provider.id not in approved]
        if excluded:
            names = ", ".join(f"{s.provider.name} ({format_bytes(s.conditional_bytes)})"
                              for s in excluded)
            body += (f"\n\nNot included without approval: {names}. "
                     "Tick their 'Include' box to add them.")
        dlg = Adw.AlertDialog.new("Clean all cache?", body)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("clean", "Clean")
        dlg.set_response_appearance("clean", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d, r: self._start_clean(
            eligible | approved, approved) if r == "clean" else None)
        dlg.present(self)

    def _clean_one(self, provider_id: str) -> None:
        scan = self.report.by_id(provider_id) if self.report else None
        if not scan:
            return
        if scan.conditional_bytes > 0:
            # E-014: provider has (partly) approval-requiring data — offer an
            # explicit choice instead of silently skipping it
            dlg = Adw.AlertDialog.new(
                f"Clean {scan.provider.name}?",
                f"{format_bytes(scan.eligible_bytes)} is regenerable cache and "
                f"can be cleaned now.\n"
                f"{format_bytes(scan.conditional_bytes)} additionally requires "
                f"your explicit approval.\n\n{scan.provider.explain()}")
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("safe", "Clean regenerable")
            dlg.add_response("all", "Clean all")
            dlg.set_response_appearance("safe", Adw.ResponseAppearance.DESTRUCTIVE)
            dlg.set_response_appearance("all", Adw.ResponseAppearance.DESTRUCTIVE)

            def on_response(_d, r):
                if r == "safe":
                    self._start_clean({provider_id}, set())
                elif r == "all":
                    self._start_clean({provider_id}, {provider_id})
            dlg.connect("response", on_response)
            dlg.present(self)
            return
        self._start_clean({provider_id}, set())

    def _start_clean(self, ids: set[str], include: set[str]) -> None:
        if self._busy or not self.report:
            return
        self._busy = True
        self.cancel_event.clear()
        self.clean_btn.set_sensitive(False)
        self._set_state(State.CLEANING)
        self._progress(0.0, "Preparing cleanup…")
        threading.Thread(target=self._clean_worker, args=(ids, include),
                         daemon=True).start()

    def _clean_worker(self, ids: set[str], include: set[str]) -> None:
        try:
            out = self.engine.clean(
                self.report, cancel=self.cancel_event,
                progress=lambda f, m: GLib.idle_add(self._progress, f, m),
                provider_ids=ids, include_conditional=include)
            GLib.idle_add(self._on_clean_done, out)
        except Exception as exc:                       # noqa: BLE001
            log.log_event(_logger, "clean_fatal", error=str(exc), level=40)
            GLib.idle_add(self._on_scan_fatal, str(exc))

    def _on_clean_done(self, out: CleanReport) -> bool:
        self._busy = False
        # results panel (rule 1): before / removed / remaining / counts
        children = []
        child = self.results_inner.get_first_child()
        while child is not None:
            children.append(child)
            child = child.get_next_sibling()
        for child in children[1:]:                     # keep the title label
            self.results_inner.remove(child)
        self.results_inner.append(build_report_panel(out))
        self.results_holder.set_visible(True)
        if out.cancelled:
            state = State.FINISHED
        elif out.failed:
            state = State.PARTIAL
        else:
            state = State.FINISHED
        self._set_state(state)
        if out.after_bytes is not None:
            self.total_label.set_label(format_bytes(out.after_bytes))
            self.sub_label.set_label("remaining after cleanup (fresh scan) — "
                                     "rescanning for updated provider list…")
        self.start_scan()          # automatic post-cleanup rescan (rules 1, 6)
        return False

    # ----------------------------------------------------------------- about
    def _show_about(self, _action, _param) -> None:
        about = Adw.AboutWindow(
            application_name=APP_NAME,
            application_icon="cachecleaner",
            developer_name="samasadul124-ui",
            version=__version__,
            comments="Safe cache discovery & cleanup for EndeavourOS / Arch Linux",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/samasadul124-ui/Arch-cache-cleaner-with-GUI",
        )
        about.present(self)
