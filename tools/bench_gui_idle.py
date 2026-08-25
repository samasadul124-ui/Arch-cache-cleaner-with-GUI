#!/usr/bin/env python3
"""GUI idle benchmark: boot the real app, wait for Ready + settle, print RSS.

Run under Xvfb:   xvfb-run -a /usr/bin/python3 tools/bench_gui_idle.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp(prefix="cc-guiperf-")
home = os.path.join(tmp, "home")
os.makedirs(os.path.join(home, ".cache", "demo"))
with open(os.path.join(home, ".cache", "demo", "x"), "wb") as f:
    f.write(b"x" * 1024)
os.environ["HOME"] = home
for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
    os.environ.pop(var, None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gi.repository import GLib  # noqa: E402
from cachecleaner.gui.app import CacheCleanerApp  # noqa: E402


def rss_kib(pid: int) -> int:
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return -1


app = CacheCleanerApp()
pid = os.getpid()
out: dict = {}


def checker() -> None:
    t_boot = time.time()
    deadline = t_boot + 30
    while time.time() < deadline:
        win = app.window
        if win is not None and win.report is not None and not win._busy:
            break
        time.sleep(0.1)
    out["startup_s"] = time.time() - t_boot
    time.sleep(5)                      # settle → idle state
    out["idle_rss_mib"] = rss_kib(pid) / 1024.0
    GLib.idle_add(app.quit)


threading.Thread(target=checker, daemon=True).start()
rc = app.run([])
print(f"GUI startup: {out.get('startup_s', -1):.2f} s | "
      f"idle RSS: {out.get('idle_rss_mib', -1):.1f} MiB | rc={rc}")
sys.exit(rc)
