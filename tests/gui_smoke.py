"""Headless GUI smoke test — run under Xvfb:

    xvfb-run -a /usr/bin/python3 tests/gui_smoke.py

Boots the REAL application against a synthetic home, waits for the async
scan, verifies dashboard/list, then exercises the advanced sweep's
Select all / Select none buttons. Never touches the real home directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp(prefix="cc-smoke-")
home = os.path.join(tmp, "home")
cache = os.path.join(home, ".cache")
os.makedirs(os.path.join(cache, "pip"))
with open(os.path.join(cache, "pip", "wheel.whl"), "wb") as f:
    f.write(b"x" * 12_345)
os.makedirs(os.path.join(cache, "myapp"))
with open(os.path.join(cache, "myapp", "c.bin"), "wb") as f:
    f.write(b"x" * 1_000)

os.environ["HOME"] = home
for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
    os.environ.pop(var, None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gi.repository import GLib  # noqa: E402

from cachecleaner.gui.app import CacheCleanerApp  # noqa: E402

app = CacheCleanerApp()
result: dict = {}


def checker() -> None:
    deadline = time.time() + 30
    win = None
    while time.time() < deadline:
        win = app.window
        if win is not None and win.report is not None and not win._busy:
            break
        time.sleep(0.2)
    if win is None or win.report is None:
        result["error"] = "window or scan did not come up in 30 s"
        GLib.idle_add(app.quit)
        return
    rows = 0
    i = 0
    while win.list.get_row_at_index(i) is not None:
        rows += 1
        i += 1
    result["total"] = win.total_label.get_label()
    result["rows"] = rows
    result["state"] = win.state_label.get_label()

    # ---- advanced sweep: toggle on, then Select all / Select none
    GLib.idle_add(win.adv_switch.set_active, True)
    dl = time.time() + 20
    while time.time() < dl:
        if getattr(win, "_sweep_checks", None) and win.adv_holder.get_visible():
            break
        time.sleep(0.2)
    checks = getattr(win, "_sweep_checks", [])
    if not checks:
        result["error"] = "advanced card did not populate"
        GLib.idle_add(app.quit)
        return
    GLib.idle_add(lambda: win.adv_select_all_btn.emit('clicked'))
    dl = time.time() + 10
    while time.time() < dl and not all(cb.get_active() for cb, _ in checks):
        time.sleep(0.1)
    result["select_all"] = all(cb.get_active() for cb, _ in checks)
    GLib.idle_add(lambda: win.adv_select_none_btn.emit('clicked'))
    dl = time.time() + 10
    while time.time() < dl and any(cb.get_active() for cb, _ in checks):
        time.sleep(0.1)
    result["select_none"] = not any(cb.get_active() for cb, _ in checks)
    GLib.idle_add(app.quit)


threading.Thread(target=checker, daemon=True).start()
rc = app.run([])

print(f"GUI SMOKE RESULT: rc={rc} {result}")
assert rc == 0, f"app exit code {rc}"
assert "error" not in result, result
assert result["rows"] >= 2, result
assert result["total"] not in ("", "—"), result
win = app.window
pip_scan = win.report.by_id("lang.pip")
assert pip_scan is not None and pip_scan.size_bytes == 12_345, pip_scan
assert result.get("select_all") is True, result
assert result.get("select_none") is True, result
print("GUI SMOKE TEST PASS (incl. Select all / Select none)")
