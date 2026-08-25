# Cache Cleaner — Architecture & Technology Decision

Version: 0.1.0 · Target: EndeavourOS / Arch Linux (extensible to other distros)

---

## 1. Goals & constraints

| Requirement | Value |
|---|---|
| Installed size | < 50 MB (target) |
| Idle RAM | as low as practical |
| GUI | modern, native Linux look, responsive during scan/clean |
| Permissions | runs as normal user; isolated, minimal elevation only when needed |
| Safety | classification system; nothing destructive without validation |
| Packaging | native Arch package `*.pkg.tar.zst`, `.desktop` launcher, icon |

## 2. Technology decision

### 2.1 Candidates evaluated

| Criterion | **A. Rust + GTK4/libadwaita** | **B. Electron** | **C. Python 3 + GTK4/libadwaita (PyGObject)** ✔ chosen |
|---|---|---|---|
| Installed size | excellent (~10 MB static binary) | ✗ ≥ 150 MB runtime | excellent (app code < 1 MB; runtime is system `gtk4`/`libadwaita`/`python-gobject` packages already in Arch repos) |
| Idle RAM | best (~25–40 MB) | ✗ > 200 MB | good (~60–90 MB) |
| Native Linux integration | full | poor (web runtime) | full — same toolkit as GNOME/Adwaita system apps |
| Modern GUI | yes (libadwaita) | yes | yes (libadwaita) |
| Filesystem/API access | yes | via Node, sandboxed | yes, unrestricted stdlib |
| Packaging on Arch | good (PKGBUILD + cargo) | poor (bundled runtime) | trivial (install pure-Python files + desktop entry) |
| Verifiable in this dev workspace | ✗ **no Rust toolchain available; gtk4-rs also needs GTK4 dev headers to even compile; nothing could be built or tested here** | ✗ violates size/RAM rules | ✔ Python 3.13 present; `python3-gi` + GTK4 + libadwaita + xvfb installable, so the GUI can be built **and smoke-tested headless** |
| Maintainability | high, steep toolchain | low | high, huge ecosystem |

### 2.2 Decision and tradeoffs

**Chosen: Option C — Python 3 + GTK4 + libadwaita via PyGObject.**

* Why not Rust (the spec's example): the development sandbox for this project has **no Rust toolchain and no GTK4 development headers**, so a Rust/GTK4 implementation could not be compiled or tested here. Per the project rules ("do not claim something works until it has actually been tested"), shipping untestable Rust code is not acceptable. Rust remains the best *runtime* option and the provider/engine layer is deliberately written so it could be ported module-by-module later.
* Why not Electron: fails the <50 MB and low-RAM requirements outright; rejected.
* Accepted tradeoffs of Python: ~2× the idle RAM of Rust and ~250–400 ms startup. Measured values are recorded in `PERFORMANCE.md`. Mitigations: lazy imports in the GUI, no third-party runtime dependencies (PyGObject binds the system GTK — nothing bundled), all scanning/cleaning off the main thread.
* All filesystem work is I/O-bound, so worker **threads** (GIL released during syscalls) give true parallelism for scanning without multiprocessing overhead.

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│ GUI layer (cachecleaner/gui) — GTK4 + libadwaita            │
│   app.py · window.py · provider_row.py · results.py         │
│   (thin view; never touches the filesystem directly)        │
├─────────────────────────────────────────────────────────────┤
│ CLI layer (cachecleaner/cli.py) — headless scan/clean/JSON  │
├─────────────────────────────────────────────────────────────┤
│ Engine (cachecleaner/core/engine.py)                        │
│   scan orchestration · clean plan · dry-run · execution     │
│   per-provider error isolation · fresh post-clean rescan    │
│   cancellation token · progress callbacks                   │
├─────────────────────────────────────────────────────────────┤
│ Provider registry (cachecleaner/providers/)                 │
│   xdg.py · browsers.py · pkgman.py · langtools.py ·         │
│   electron.py  +  discovery-driven dynamic providers        │
├─────────────────────────────────────────────────────────────┤
│ Core primitives (no GTK imports — fully unit-testable)      │
│   provider.py (interface) · safety.py (path validation +    │
│   SafetyLevel) · fs.py (streaming size/delete) · errors.py  │
│   (classified errors) · log.py (structured logs) · units.py │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** adding a new cache source = adding a `CacheProvider` subclass and registering it. No UI or engine changes.

## 4. CacheProvider interface

```python
class CacheProvider(ABC):
    id: str                  # stable machine id, e.g. "browser.firefox"
    name: str                # human readable, e.g. "Firefox"
    category: Category       # BROWSER / PACKAGE_MANAGER / LANG_TOOL / APP / SYSTEM / DEV
    safety: SafetyLevel      # SAFE_CACHE | CONDITIONAL_CACHE | DO_NOT_DELETE

    def detect(self) -> bool                 # is this software/cache present?
    def cache_paths(self) -> list[CachePath] # concrete paths + per-path safety + purpose
    def calculate_size(self) -> int          # measured bytes via fs.dir_size()
    def clean(self, dry_run, cancel) -> CleanResult   # delete (or plan), per-path errors
    def verify(self) -> VerifyResult         # post-clean remeasure + invariant checks
    def explain(self) -> str                 # UI text: what will be removed & impact
```

## 5. Safety model

### 5.1 Classification
* **SAFE_CACHE** — pure derived data, always regenerable (browser disk caches, thumbnail caches, `pip cache`, `npm cache`, `/var/cache/pacman/pkg` packages, …). Auto-clean allowed.
* **CONDITIONAL_CACHE** — regenerable but costly or ambiguous (pnpm store, cargo registry `src`, AUR build caches, flatpak unused data). Cleaned **only with explicit per-provider approval**; the UI shows `explain()` first.
* **DO_NOT_DELETE** — detected but protected (browser profiles/databases/keyrings, Telegram `tdata`, `~/.ccache` off-limits patterns, anything failing path validation). Listed as "0 B protected", never touched.

### 5.2 Hard never-delete list
user documents, downloads, application databases, credentials/keyrings, browser
profiles (only their cache subdirs are eligible), Telegram session data (`tdata`),
encryption keys (`*.gnupg`, ssh), configuration files, package databases
(`/var/lib/pacman`), anything under `/boot`, `/etc`, `/usr`, `/lib*`, `/bin`, `/sbin`.

### 5.3 Path validation (`core/safety.py`) — applied to *every* path before delete
1. non-empty, absolute, normalized (`normpath`, no `..`);
2. not `/`, `/home`, `$HOME` itself, and not shallower than the minimum depth;
3. real-path containment: `realpath(path)` must stay inside an allowed cache root (defeats symlink traversal);
4. the symlink-aware guard never *follows* links pointing outside the root — they are unlinked, not traversed;
5. name denylist (`tdata`, `keyring`, `wallet`, `databases`, `IndexedDB`, `Local Storage`, `.gnupg`, …) rejects paths even inside allowed roots;
6. per-provider allowlist of cache roots (XDG cache home, `~/.npm`, `~/.cache`, specific `~/.local/share` subpaths, `/var/cache/pacman/pkg`, …).

Every rule has explicit tests (see `tests/test_safety.py`).

## 6. Layered discovery strategy (no full-disk scans)

1. **Known safe cache locations** — static, high-confidence paths (XDG cache home subdirs, thumbnails, shader caches).
2. **Known application cache patterns** — per-provider patterns for browsers, dev tools, Electron apps.
3. **Installed-software discovery** — consult `pacman -Qq` (if present), `PATH` binaries (`shutil.which`), and known config dirs to enable/disable conditional providers.
4. **User-directory targeted discovery** — enumerate *direct children* of `~/.cache`, `~/.config/*/Cache*`, `~/.var/app/*/cache` (flatpak); unknown children become a grouped "Other application caches" provider, still validated.
5. **Optional advanced scan** — opt-in only; never runs by default.

## 7. Cleaning engine behaviour

```
scan() → plan (sizes + safety) → [UI confirmation] →
clean providers incrementally (threadpool, per-provider try/except, cancel token) →
fresh_scan()  ← "remaining" is ALWAYS remeasured, never computed as before-minus-removed →
report(before, removed=before−remaining*, providers_cleaned, skipped, errors, per-provider details)
```
*`removed` is derived from two real measurements (before scan and post-clean fresh scan), plus per-provider byte counts for the detail view.

* **Dry-run mode**: identical pipeline, deletion replaced by "would delete" plan; used by tests and exposed via CLI (`--dry-run`).
* **Errors** are classified (`errors.py`: PERMISSION_DENIED, PATH_VANISHED, FILE_IN_USE, INVALID_PATH, BROKEN_SYMLINK, INSUFFICIENT_PRIVILEGES, FILESYSTEM_ERROR, PROVIDER_FAILURE) and never abort the whole run.

## 8. Threading / responsiveness

* GTK main thread never does I/O. Scanning & cleaning run in a `ThreadPoolExecutor` (workers = CPU count, capped).
* Progress flows through a thread-safe queue, drained into the UI with `GLib.idle_add`.
* Cancellation: `threading.Event` checked between files/dirs; clean stops within milliseconds.

## 9. Permissions model

* App runs as the **normal user**. All user-level caches (the vast majority) need no elevation.
* System caches (`/var/cache/pacman/pkg`) are owned by root: the provider reports them read-only and, on request, delegates deletion to a **separate minimal helper** (`cachecleaner-paccache`, ~40 lines) invoked via `pkexec`/polkit so authentication is requested once, only for that isolated step. The GUI itself is never run as root.

## 10. Logging

Python `logging`, structured key=value lines, file at `$XDG_STATE_HOME/cachecleaner/cachecleaner.log`
(default `~/.local/state/cachecleaner/`). Logged: scan start/end, provider discovery, sizes,
clean start/end, per-deletion errors, skipped items, final totals. Never logged: file contents,
credentials, tokens; paths are logged verbatim but never file bodies.

## 11. Packaging (Arch / EndeavourOS)

* `packaging/PKGBUILD` → `cachecleaner-<ver>-any.pkg.tar.zst` (pure-Python, `arch=('any')`),
  depends: `python`, `python-gobject`, `gtk4`, `libadwaita`, `hicolor-icon-theme`;
  optdepends: `polkit` (for the pacman-cache helper).
* Installs: `/usr/bin/cachecleaner`, Python package under site-packages,
  `/usr/share/applications/cachecleaner.desktop`, SVG icon under
  `/usr/share/icons/hicolor/scalable/apps/`.
* Dev run: `python -m cachecleaner` from the repo (no install needed).
* NOTE: the dev sandbox is Debian — the actual `.pkg.tar.zst` must be built on Arch with
  `makepkg`; the PKGBUILD is written and lint-checked but the binary package is produced
  on the target system (documented in README, not faked).

## 12. Testing strategy

* `pytest`, all fixtures in `tmp_path` — **never** against the real `$HOME`.
* Test isolation: `HOME`/`XDG_CACHE_HOME` monkeypatched to fixtures.
* Matrix (rule 15): empty/small/huge cache, missing dir, permission denied, symlinks,
  broken symlinks, file-disappears-during-scan, cache-recreated-during-clean,
  multi-provider failure, partial cleanup, no-cache, cancellation, interrupted clean,
  elevation-required reporting, large tree.
* Safety tests (rule 16): `/`, `/home`, `$HOME`, empty, `..` traversal, symlink escape.
* GUI: headless smoke test under Xvfb (window constructs, scan renders, no crash).

## 13. Performance targets (measured in `PERFORMANCE.md`)

binary/installed size · startup time · idle RAM · scan RAM/CPU · clean CPU — all measured, never estimated.

## 14. Repository layout

```
cache-cleaner/
├── ARCHITECTURE.md · README.md · TASK_LOG.md · ERRORS.md · PERFORMANCE.md
├── pyproject.toml
├── cachecleaner/
│   ├── __init__.py · __main__.py · cli.py
│   ├── core/    __init__.py units.py errors.py safety.py fs.py
│   │            provider.py log.py discovery.py engine.py
│   ├── providers/ __init__.py xdg.py browsers.py pkgman.py
│   │              langtools.py electron.py
│   └── gui/     __init__.py app.py window.py provider_row.py results.py
├── data/        cachecleaner.desktop · icons/hicolor/scalable/apps/cachecleaner.svg
├── packaging/   PKGBUILD
└── tests/       test_units.py test_safety.py test_fs.py test_providers.py
                 test_engine.py test_cli.py test_gui_smoke.py
```

## 15. Versioning

Semantic versioning, starting at **0.1.0**. Not production-ready until: destructive ops tested,
safety rules tested, package creation succeeds, launcher works, UI works, post-clean
verification works, error logging works.
