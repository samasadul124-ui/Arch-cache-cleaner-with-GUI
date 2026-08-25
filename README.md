# Cache Cleaner

A modern, **safe** cache-cleaning utility for **EndeavourOS / Arch Linux**.
It discovers cache data on your computer, shows exactly how much there is,
lets you clean it with one click, and immediately re-measures the filesystem
to report the real result.

Built with **GTK 4 + libadwaita** — a native Linux app, no web runtime, no
bundled dependencies. Installed payload: **~100 KiB** (target was < 50 MB).

![status](https://img.shields.io/badge/version-0.1.0-blue)

## Features

* **Dynamic cache discovery** — not a hard-coded list: browsers (Firefox,
  Chrome, Chromium, Brave, Edge, Vivaldi, Opera), package managers (pacman,
  yay, paru, flatpak), dev tools (npm, pnpm, yarn, pip, Go, Cargo, rustup,
  ccache, Gradle, Maven), VS Code/VSCodium, other Electron apps, thumbnails,
  fontconfig, Mesa/GPU shader caches, KDE sycoca — plus every unclaimed
  folder in `~/.cache` (XDG contract).
* **Measured, never estimated** — sizes come from real filesystem traversal.
* **Safety classification** — every location is `SAFE_CACHE`,
  `CONDITIONAL_CACHE` (needs your explicit approval) or `DO_NOT_DELETE`.
  Documents, configs, credentials, browser profiles, Telegram sessions,
  package databases and anything needed to boot Linux are structurally
  unreachable by the cleaner.
* **Clean All with live progress**, per-provider cleaning, cancellation,
  dry-run, and a full report: before / removed / remaining (fresh scan) /
  cleaned / skipped / errors.
* **Runs as a normal user.** Cleaning the root-owned pacman package cache
  triggers the **system polkit authentication dialog** from inside the app —
  the isolated ~40-line audited helper does the privileged work, the GUI
  itself never runs as root, and the app never asks for, sees or stores your
  password (see *System (pacman) cache* below).

## System (pacman) cache — how elevation works

`/var/cache/pacman/pkg` belongs to root, so it is handled as a first-class
provider with explicit privilege escalation:

```
Open Cache Cleaner → scan → pacman cache detected (real size shown)
   → you click Clean (or include it via approval + Clean All)
   → app detects root ownership
   → system authentication dialog appears (polkit/pkexec)
   → you authenticate with the OS dialog (never inside this app)
   → isolated helper deletes the cache
   → app rescans and reports measured Before / Removed / After
```

* Cancel the dialog → “Pacman cache cleanup cancelled.” — nothing modified.
* Wrong password/denied → “Authentication failed. Pacman cache was not
  modified.”
* Files left behind → reported as “completed with errors” with exact
  Removed/Remaining amounts — success is never claimed when files remain.

By default the full cache is removed (matching the size shown in the UI). To
keep the 2 newest versions of every package instead (downgrade safety):
`pkexec cachecleaner-paccache 2`.

## Install (EndeavourOS / Arch)

```bash
git clone https://github.com/samasadul124-ui/cache-cleaner
cd cache-cleaner/packaging
makepkg -si          # builds cachecleaner-0.1.1-any.pkg.tar.zst and installs
```

> v0.1.1 fixes a fresh-install build failure (E-010: the PKGBUILD now
> resolves the GitHub archive's `cache-cleaner-<version>` source directory
> independently of the package name) and wires real polkit privilege
> escalation for the pacman cache (E-011).

Then launch **"Cache Cleaner"** from your application menu, or run
`cachecleaner`.

Dependencies (all from the official repos): `python`, `python-gobject`,
`gtk4`, `libadwaita`, `hicolor-icon-theme`. Optional: `polkit` (pacman-cache
helper), `pacman-contrib` (alternative `paccache`).

> Building the package requires Arch/EndeavourOS (`makepkg`). The PKGBUILD is
> committed and lint-checked; CI/build machines on other distros can run the
> app directly as shown below but cannot produce the `.pkg.tar.zst`.

## Run from source (development)

```bash
python -m cachecleaner            # GUI (needs GTK4 + libadwaita + PyGObject)
python -m cachecleaner --scan     # headless scan
python -m cachecleaner --dry-run  # what would be deleted, nothing touched
python -m cachecleaner --clean --yes
```

Useful flags: `--json` (machine-readable), `--providers id1,id2`,
`--include-conditional id` (explicit approval), `--home DIR` (test against
another home), `--verbose`.

## How safety works

Before anything is deleted, every path passes a validator that rejects: `/`,
`/home`, `$HOME`, relative paths, `..` traversal, paths outside the allowed
cache roots, symlink escapes (checked via `realpath`), and denylisted names
(`tdata`, keyrings, `IndexedDB`, `cookies.*`, …). Deletion never follows
symlinks and removes only the *contents* of validated cache roots.

Conditional caches (pnpm store, cargo registry sources, ccache, Gradle,
Maven, flatpak, pacman) are only cleaned when you tick **Include** or pass
`--include-conditional`, after reading the explanation.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the technology decision, provider
interface, threading model and permissions design. Performance numbers are in
[PERFORMANCE.md](PERFORMANCE.md); development history in
[TASK_LOG.md](TASK_LOG.md) and [ERRORS.md](ERRORS.md).

## Tests

```bash
python -m pytest                                  # 124 core/CLI tests
xvfb-run -a python3 tests/gui_smoke.py            # headless GUI boot test
python3 tools/bench_cli.py                        # engine benchmarks
```

Tests run exclusively in isolated temporary fixtures — the test suite never
deletes anything from a real home directory.

## Project status

Version **0.1.1** — bugfix release over 0.1.0 (PKGBUILD source-directory
coupling fixed with regression tests; pacman cache cleaning now performs real
polkit authentication with measured before/after verification). Feature-
complete for the initial goal set and tested, but not yet battle-hardened on
many real user machines. Report issues on the GitHub issue tracker.

## License

GPL-3.0-or-later.
