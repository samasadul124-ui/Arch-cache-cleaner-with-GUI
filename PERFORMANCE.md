# Performance measurements (measured, never estimated — rules 8, 23)

Environment: Debian 13 sandbox, Python 3.13, GTK 4.18, libadwaita 1.7, Xvfb
software rendering (no GPU). Repeat on native Arch for shipping numbers.

## Installed size

| Item | Measured |
|---|---|
| App payload installed by PKGBUILD (Python package + icon + .desktop) | **100.9 KiB** |
| `cachecleaner/` source (23 modules, ~2,700 LOC) | 100.9 KiB |
| `data/` (icon + desktop) | 2.4 KiB |
| Target budget | < 50 MB ✅ exceeded by ~500× |

The runtime footprint is dominated by shared system libraries (`gtk4`,
`libadwaita`, `python3`, `python-gobject`) that Arch already ships and other
apps reuse — nothing is bundled. The package itself is `arch=('any')` pure
Python.

## Startup time

| Entry | Measured |
|---|---|
| `cachecleaner --version` (CLI, cold) | **69 ms** |
| `cachecleaner --scan` (empty home) | **70 ms** |
| GUI to "Ready" (first scan complete, Xvfb) | **1.10 s** |

CLI startup is fast because GTK/GLib are imported **lazily** — the headless
path never loads the toolkit. GUI startup includes GTK/Adwaita init plus the
first filesystem scan.

## Memory (RSS)

| Scenario | Measured |
|---|---|
| Engine idle at start | 15.5 MiB |
| After scanning 15,000 files / 117 MiB | 16.2 MiB (**+0.6 MiB**) |
| After cleaning those files | 16.2 MiB (no growth) |
| GUI idle (app, settled) | 212 MiB |
| Bare GTK4+Adw window (no app code, baseline) | 177 MiB |
| **GUI overhead attributable to this app** | **≈ 35 MiB** |

The scanner/deleter are streaming (`os.scandir`, iterative stack, no file
bodies read, no retained file lists), so engine RSS stays flat regardless of
cache size — confirmed by the +0.6 MiB figure over 117 MiB of files. GUI RAM
is dominated by the toolkit itself, shown by the bare-window baseline.

## Scan / clean throughput (engine, in-process)

| Fixture | Scan | Clean |
|---|---|---|
| 1,000 files / 3.9 MiB | 0.005 s (206k files/s) | 0.01 s (126k files/s) |
| 15,000 files / 117 MiB | **0.05 s (294k files/s)** | **0.12 s (130k files/s)** |

Every benchmark asserts correctness: `before == removed` and fresh-scan
`after == 0` after a clean.

## Reproduce

```
python3 tools/bench_cli.py [dirs] [files_per_dir] [file_bytes]   # engine
xvfb-run -a python3 tools/bench_gui_idle.py                      # GUI idle RSS
```

## Interpretation vs the <50 MB target

* **Installed size: 100.9 KiB** — the target is met with very large margin.
* **Idle RAM:** the GUI's 212 MiB is GTK4/libadwaita's cost, not the cleaner's;
  the cleaning engine itself adds ~35 MiB and scales O(1) with cache size.
  If the RAM ceiling matters more than the native GUI, the identical engine is
  available headlessly (`cachecleaner --scan/--clean`, ~16 MiB).
