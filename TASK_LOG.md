# TASK_LOG — cache-cleaner

Task-by-task development journal. Every completed task is recorded here before the
next one starts. Errors encountered are mirrored into `ERRORS.md` with full detail.

---

## Task 1 — Repository bootstrap
- **Task:** Create GitHub repository, local git repo, `.gitignore`, and the mandatory journals (`TASK_LOG.md`, `ERRORS.md`).
- **File:** `.gitignore`, `TASK_LOG.md`, `ERRORS.md`
- **Purpose:** All subsequent work must be committed per task; journals are required to record tasks/errors from the very first step.
- **Changes:** Repo `cache-cleaner` created on GitHub (public) via API; local repo initialized on `main`; remote configured; bootstrap files written.
- **Tests:** `git push` succeeds to `origin/main` (remote is empty until this commit).
- **Errors:** E-001 — first bootstrap attempt failed (shell error, 123 ms) because the tool call used `cwd=/home/user/cache-cleaner` before that directory existed. See `ERRORS.md`.
- **Resolution:** Re-ran the bootstrap with `cwd=/home/user`, creating the directory inside the script.
- **Result:** Repository ready for one-file-at-a-time development.
- **Git commit:** `task: initialize repository, gitignore and project journals`
- **Next task:** `ARCHITECTURE.md` — technology decision and system design (required before any source file).

## Task 2 — Architecture & technology decision
- **Task:** Write the architecture/design document before any source file (rules 9, 24).
- **File:** `ARCHITECTURE.md`
- **Purpose:** Document the technology choice, provider architecture, safety model, threading, packaging, testing strategy.
- **Changes:** Full architecture document: Python 3 + GTK4/libadwaita chosen; Rust rejected for this workspace (no toolchain → untestable here); Electron rejected (size/RAM); safety classification, path-validation rules, layered discovery, engine flow, permissions model, packaging plan.
- **Tests:** Markdown structure verified (`wc -l`, headers present).
- **Errors:** None.
- **Resolution:** n/a
- **Result:** Design baseline committed.
- **Git commit:** `task: add architecture and technology decision document`
- **Next task:** `pyproject.toml` — project metadata (name, version 0.1.0, entry points).

## Task 3 — Project metadata
- **Task:** Define package metadata, version 0.1.0, entry point.
- **File:** `pyproject.toml`
- **Purpose:** Fix name/version/entry point before writing package code; document zero-pip-dependency runtime.
- **Changes:** Created setuptools-based `pyproject.toml` (version 0.1.0, console script `cachecleaner`, pytest config).
- **Tests:** Parsed with `tomllib`; asserted name/version/entry point → PASS.
- **Errors:** None.
- **Resolution:** n/a
- **Result:** Metadata valid.
- **Git commit:** `task: add pyproject metadata (version 0.1.0)`
- **Next task:** `cachecleaner/__init__.py` — package root with version constant.

## Task 4 — Package root
- **Task:** Create package root with version/identity constants.
- **File:** `cachecleaner/__init__.py`
- **Purpose:** Establish importable package; keep GTK out of package import path.
- **Changes:** `__init__.py` with `__version__`, `APP_ID`, `APP_NAME`.
- **Tests:** `python3 -c "import cachecleaner"` → PASS (no GTK needed).
- **Errors:** None.
- **Resolution:** n/a
- **Result:** Package importable headless.
- **Git commit:** `task: add package root module`
- **Next task:** `cachecleaner/core/units.py` — byte formatting helpers.

## Task 5 — core subpackage root
- **Task:** Create `cachecleaner/core/__init__.py`.
- **File:** `cachecleaner/core/__init__.py`
- **Purpose:** Establish headless-safe core subpackage.
- **Changes:** Docstring module, no imports.
- **Tests:** covered by package import in Task 6 run.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add core subpackage root`
- **Next task:** `cachecleaner/core/units.py`.

## Task 6 — Byte/duration formatting helpers
- **Task:** Human-readable size/duration formatting used by GUI, CLI and reports.
- **File:** `cachecleaner/core/units.py`
- **Purpose:** UI needs 'GiB' style labels; reports need durations. Pure functions, no I/O.
- **Changes:** `format_bytes`, `parse_size`, `format_duration` with NaN/negative guards.
- **Tests:** executed with Task 7's test file (see below).
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add byte/duration formatting helpers`
- **Next task:** `tests/test_units.py`.

## Task 7 — Unit tests for formatting helpers
- **Task:** Test matrix for units module.
- **File:** `tests/test_units.py`
- **Purpose:** Lock down formatting behaviour (zero, KiB/MiB/GiB/TiB, negatives, NaN, parsing, durations).
- **Changes:** 18 test cases.
- **Tests:** `pytest tests/test_units.py` → all passed.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add unit tests for formatting helpers`
- **Next task:** `cachecleaner/core/errors.py` — classified error types.

## Task 8 — Classified error types
- **Task:** Implement error classification (rule 12).
- **File:** `cachecleaner/core/errors.py`
- **Purpose:** Every scanner/cleaner error gets a kind, user-facing message, and loggable detail; never swallowed.
- **Changes:** `ErrorKind` (10 kinds), `CleanError`, `classify()` mapping errno→kind, `user_message()`, `ErrorBucket` accumulator collapsing repeats.
- **Tests:** run with Task 9's suite.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add classified error types and error bucket`
- **Next task:** `tests/test_errors.py`.

## Task 9 — Error classification tests
- **Task:** Test errno→kind mapping, symlink distinction, bucket collapsing.
- **File:** `tests/test_errors.py`
- **Purpose:** Guarantee stable classification (UI text depends on it).
- **Changes:** 16 test cases incl. parametrized message coverage for every kind.
- **Tests:** `pytest tests/test_errors.py` → all passed.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add tests for error classification`
- **Next task:** `cachecleaner/core/safety.py` — path validation & safety levels.

## Task 10 — Safe path validator
- **Task:** Implement safety model core: SafetyLevel classification + PathSafety validator.
- **File:** `cachecleaner/core/safety.py`
- **Purpose:** Nothing may be deleted without passing validation (rules 5.3, 16).
- **Changes:** `SafetyLevel` enum; `PathSafety.validate()` with empty/relative/traversal/dangerous-prefix/$HOME/shallow/denylist/root-containment/realpath-symlink-escape checks; `default_user_roots()`.
- **Tests:** run via Task 11 suite.
- **Errors:** Design conflict found during review — `"pacman"` in the name denylist would reject the legitimate allowed root `/var/cache/pacman/pkg`.
- **Resolution:** Removed `pacman`/`local` from denylist; `/var/lib/pacman` remains protected by the `/var` dangerous-prefix rule and realpath containment.
- **Result:** committed.
- **Git commit:** `task: add safe path validator and safety levels`
- **Next task:** `tests/test_safety.py`.

## Task 11 — Path-validation safety tests
- **Task:** Explicit rule-16 test matrix.
- **File:** `tests/test_safety.py`
- **Purpose:** Prove rejections for `/`, `/home`, `$HOME`, empty, `..`, system paths, denylisted names, symlink escapes; prove acceptance of valid cache paths incl. symlinked cache roots.
- **Changes:** 30 test cases.
- **Tests:** `pytest tests/test_safety.py` → 30 passed.
- **Errors:** First draft of `test_shallow_path_rejected` built a path that was not actually shallow (deep tmp path) — fixed before commit to use `/opt/cache-root` (2 components).
- **Resolution:** Test rewritten; suite green.
- **Result:** PASS 30/30.
- **Git commit:** `task: add path-validation safety test matrix`
- **Next task:** `cachecleaner/core/fs.py` — streaming filesystem measurement & deletion.

## Task 12 — Filesystem measurement & deletion
- **Task:** Implement real size measurement + safe streaming deletion (rule 4).
- **File:** `cachecleaner/core/fs.py`
- **Purpose:** Measure bytes via lstat (never read contents), delete contents without following symlinks, survive vanishing files/permissions/concurrent recreation.
- **Changes:** `dir_size()` iterative scanner; `delete_contents()` two-phase post-order deleter with safety validation, dry-run, cancellation, throttled progress callback (`progress_every`, default 256 ops).
- **Tests:** run via Task 13 suite.
- **Errors:** Initial signature had fixed 256-op progress cadence, making cancellation tests non-deterministic.
- **Resolution:** Added `progress_every` parameter (tests use cadence 1; production keeps 256 for low overhead).
- **Result:** committed.
- **Git commit:** `task: implement filesystem scanner and streaming deletion`
- **Next task:** `tests/test_fs.py`.

## Task 13 — Filesystem engine tests
- **Task:** Cover rule-15 fixtures: empty/small/huge cache, missing dir, permission denied, symlinks, broken symlinks, vanishing file, cache recreated during clean, cancellation, dry-run, refusal, root retention.
- **File:** `tests/test_fs.py`
- **Purpose:** Prove deletion correctness + safety before any provider uses it.
- **Changes:** 19 tests incl. 1000-file tree, symlink-escape protection (target untouched), chmod-000 permission capture.
- **Tests:** `pytest tests/test_fs.py` → 19 passed.
- **Errors:** None at run time (cadence issue fixed in Task 12 before commit).
- **Resolution:** n/a
- **Result:** PASS 19/19.
- **Git commit:** `task: add filesystem engine tests (19 cases)`
- **Next task:** `cachecleaner/core/provider.py` — CacheProvider interface + result types.

## Task 14 — CacheProvider interface
- **Task:** Define provider architecture (rule 3): id/name/category/detect/cache_paths/calculate_size/clean/verify/explain + shared context.
- **File:** `cachecleaner/core/provider.py`
- **Purpose:** New cache sources plug in without UI/engine changes; defaults implement measurement/cleaning on top of validated fs primitives.
- **Changes:** `Category`, `CachePath`, `ProviderContext`, `ProviderCleanResult`, abstract `CacheProvider` with default size/clean/verify; per-path error isolation; conditional paths only cleaned on approval.
- **Tests:** py_compile + behavioural smoke: fake provider on tmp fixtures — size 2277 B measured, clean freed exactly 1500 B (eligible path), DO_NOT_DELETE path (777 B) untouched, verify() reports 777 B remaining.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add cache provider interface`
- **Next task:** `cachecleaner/core/log.py` — structured logging.

## Task 15 — Structured logging
- **Task:** Implement rule-17 logging.
- **File:** `cachecleaner/core/log.py`
- **Purpose:** Full diagnostics to file (`$XDG_STATE_HOME/cachecleaner/cachecleaner.log`), concise console output; never logs file contents.
- **Changes:** `setup_logging`, `get_logger`, `log_event` with key=value formatter and quote-escaping; file-open failure never crashes the app.
- **Tests:** Inline: wrote events to tmp log; asserted `event=scan_start providers=17 mode=full` present and space-containing paths quoted.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add structured logging`
- **Next task:** `cachecleaner/providers/__init__.py` — provider registry.

## Task 16 — XDG desktop cache providers
- **Task:** First provider module: thumbnails, fontconfig, Mesa shader cache, KDE sycoca.
- **File:** `cachecleaner/providers/xdg.py`
- **Purpose:** Cover classic regenerable desktop caches; document trash exclusion (not cache → out of scope).
- **Changes:** 4 provider classes, all SAFE_CACHE, detection via paths/binaries, UI explanations.
- **Tests:** py_compile + import check → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add XDG desktop cache providers`
- **Next task:** `cachecleaner/providers/browsers.py`.

## Task 17 — Browser cache providers
- **Task:** Firefox + Chrome/Chromium/Brave/Edge/Vivaldi/Opera cache providers.
- **File:** `cachecleaner/providers/browsers.py`
- **Purpose:** Clean browser disk caches without ever touching profiles/databases/credentials.
- **Changes:** `FirefoxProvider` targets only `cache2` per profile (classic + XDG + flatpak locations); `_ChromiumProvider` base targets only 7 known cache subdirs per profile.
- **Tests:** py_compile → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add browser cache providers (Firefox + Chromium family)`
- **Next task:** `cachecleaner/providers/pkgman.py`.

## Task 18 — Package-manager cache providers
- **Task:** pacman, yay, paru, flatpak providers.
- **File:** `cachecleaner/providers/pkgman.py`
- **Purpose:** Cover Arch package caches with correct safety/elevation semantics.
- **Changes:** pacman → CONDITIONAL_CACHE + `needs_elevation()` + paccache advice; yay/paru SAFE; flatpak CONDITIONAL with `flatpak uninstall --unused` guidance.
- **Tests:** py_compile → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add package-manager cache providers`
- **Next task:** `cachecleaner/providers/langtools.py`.

## Task 19 — Language toolchain cache providers
- **Task:** npm, pnpm, yarn, pip, Go, Cargo, rustup, ccache, Gradle, Maven.
- **File:** `cachecleaner/providers/langtools.py`
- **Purpose:** Cover dev-tool caches with graded safety (pip/npm/go SAFE; pnpm store/ccache/gradle/maven CONDITIONAL).
- **Changes:** Declarative `_SimpleProvider` base; Cargo splits registry/cache (SAFE) vs registry/src (CONDITIONAL); `extra_cache_roots` hook for out-of-~/.cache locations.
- **Tests:** py_compile → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add language toolchain cache providers`
- **Next task:** `cachecleaner/providers/electron.py`.

## Task 20 — Electron app cache providers
- **Task:** VS Code, VSCodium, dynamic generic-Electron provider.
- **File:** `cachecleaner/providers/electron.py`
- **Purpose:** Clean Electron disk/code/GPU caches without touching accounts/settings; exclude Telegram (session data) and browsers owned by dedicated providers.
- **Changes:** `_VscodeLikeProvider` (adds workspaceStorage as CONDITIONAL), `ElectronAppsProvider` scanning `~/.config/*/{Cache,Code Cache,GPUCache,CachedData}` with explicit exclusion list.
- **Tests:** py_compile → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add Electron app cache providers with Telegram exclusion`
- **Next task:** `cachecleaner/providers/__init__.py` — provider registry.

## Task 21 — Provider registry
- **Task:** Central registry + instantiation/detection entry points.
- **File:** `cachecleaner/providers/__init__.py`
- **Purpose:** Engine and UI consume providers through one list; adding providers needs no engine/UI changes.
- **Changes:** `PROVIDER_CLASSES` (28 classes), `instantiate_all`, `detect_all` with per-provider OSError guard.
- **Tests:** (1) sandbox run → 28 unique IDs, detection executes read-only; (2) synthetic home fixture with fake Firefox/Chrome/VS Code/npm/thumbnail caches → all 5 expected providers detected.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add provider registry`
- **Next task:** `tests/test_providers.py` — provider safety + detection matrix.

## Task 22 — Provider safety & detection tests
- **Task:** Prove providers never list profile/credential/session data; cleaning frees only caches; detection matrix.
- **File:** `tests/test_providers.py`
- **Purpose:** Safety boundary is the core promise of the app — needs its own tests.
- **Changes:** 11 tests: Firefox cache2-only targeting + profile data survival; Chromium Cache/Code Cache/GPUCache-only; Telegram excluded from generic Electron scan; VS Code workspaceStorage CONDITIONAL gating; layered fixture detection; empty-fixture detection.
- **Tests:** after fixes (E-002/E-003) → full suite 105 passed.
- **Errors:** E-002 (which()-based detection noise), E-003 (expanduser env leak), E-004 (expected refusal; engine requirement captured) — all in `ERRORS.md`.
- **Resolution:** detect() requires existing cache dir; paths anchor on ctx.home; test mirrors engine allowlist behaviour.
- **Result:** PASS (105 total).
- **Git commit:** `task: add provider safety and detection tests`
- **Next task:** `cachecleaner/core/discovery.py` — layered software discovery + dynamic "other caches".

## Task 23 — Layered discovery
- **Task:** Installed-software discovery + dynamic "Other application caches" provider.
- **File:** `cachecleaner/core/discovery.py`
- **Purpose:** Rule 13 layers 3-4: use pacman/PATH data; sweep unclaimed ~/.cache children (XDG contract) without full-disk scans.
- **Changes:** `installed_packages()` (cached pacman -Qq, failure-tolerant), `claimed_cache_basenames()`, `OtherXdgCachesProvider` (skips hidden, denylisted, claimed entries; never follows symlinks).
- **Tests:** Fixture with pip/myapp/other-tool/tdata/.hidden → only myapp+other-tool offered; pip claimed by PipProvider; tdata denied.
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add layered discovery and dynamic XDG cache provider`
- **Next task:** `cachecleaner/core/engine.py` — scan/clean orchestration.

## Task 24 — Cleaning engine
- **Task:** Scan orchestration + clean plan/execute + fresh rescan + dry-run + cancellation + elevation reporting.
- **File:** `cachecleaner/core/engine.py`
- **Purpose:** Rules 5/6/14 in one coordinator consumed by both GUI and CLI.
- **Changes:** `Engine.scan()` (parallel measurement, dynamic XDG provider appended, safety allowlist extended from provider declarations), `Engine.clean()` (per-provider try/except isolation, elevation skip with INSUFFICIENT_PRIVILEGES, conditional approval set, mandatory fresh rescan), structured log events throughout.
- **Tests:** run via Task 25 suite.
- **Errors:** E-005 (dry-run removed semantics) — fixed before commit.
- **Resolution:** `removed_bytes` property branches on dry_run/rescan presence.
- **Result:** committed.
- **Git commit:** `task: implement cleaning engine with fresh-rescan verification`
- **Next task:** `tests/test_engine.py`.

## Task 25 — Engine integration tests
- **Task:** Rule-15 engine matrix: full clean, fresh rescan (rule 6), recreation-during-clean, per-provider selection, cancellation, failing-provider isolation, conditional approval, elevation skip, partial-cleanup errors, no-cache, dry-run.
- **File:** `tests/test_engine.py`
- **Purpose:** End-to-end proof of the cleaning pipeline on a synthetic home.
- **Changes:** 12 tests.
- **Tests:** full suite 117 passed.
- **Errors:** E-005 (engine), E-006 (test design), plus an `IndexError` from asserting on an elevation record that was never produced because the test patched the provider instead of the scan record — fixed by setting `ProviderScan.needs_elevation` directly.
- **Resolution:** see ERRORS.md + test edits.
- **Result:** PASS (117 total).
- **Git commit:** `task: add engine integration tests (12 scenarios)`
- **Next task:** `cachecleaner/cli.py` — headless CLI (scan/clean/dry-run/JSON).

## Task 26 — Headless CLI
- **Task:** CLI over the engine: `--scan`, `--dry-run`, `--clean`, `--json`, `--providers`, `--include-conditional`, `--home`, `--yes`.
- **File:** `cachecleaner/cli.py`
- **Purpose:** Production headless mode + the means to exercise the full pipeline in this sandbox; JSON mode for scripting.
- **Changes:** argparse front-end, human + JSON printers, confirmation prompt, exit codes (0 ok / 1 partial / 2 fatal / 130 cancelled).
- **Tests:** run via Task 28.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add headless CLI with scan/dry-run/clean and JSON reports`
- **Next task:** `cachecleaner/__main__.py`.

## Task 27 — Entry point
- **Task:** `python -m cachecleaner` dispatcher.
- **File:** `cachecleaner/__main__.py`
- **Purpose:** GUI by default; CLI when flags given, no display, or GTK missing.
- **Changes:** Graceful fallback chain with informative messages.
- **Tests:** headless sandbox run `python -m cachecleaner --scan` → exit 0, report rendered (0 providers — verified correct: sandbox ~/.cache is empty and ~/.npm absent; pre-fix smoke-test detections came from the removed which() fallback).
- **Errors:** None. **Resolution:** n/a
- **Result:** PASS.
- **Git commit:** `task: add entry point with GUI/CLI dispatch`
- **Next task:** `tests/test_cli.py`.

## Task 28 — End-to-end CLI tests
- **Task:** CLI integration matrix on isolated homes.
- **File:** `tests/test_cli.py`
- **Purpose:** Prove scan/JSON/dry-run/clean/subset/abort/version paths.
- **Changes:** 7 tests.
- **Tests:** 7 passed; full suite 124 green.
- **Errors:** First draft asserted "15.0 KiB" for 15 000 B — wrong binary-unit arithmetic (14.6 KiB); corrected before commit.
- **Resolution:** expectation fixed.
- **Result:** PASS (124 total).
- **Git commit:** `task: add end-to-end CLI tests`
- **Next task:** `cachecleaner/gui/__init__.py` — GUI subpackage (lazy GTK imports).

## Task 29-32 — GUI layer (app/window/rows/results)
- **Task:** Build the GTK4 + libadwaita interface (rule 1, 11).
- **Files:** `cachecleaner/gui/__init__.py`, `gui/app.py`, `gui/provider_row.py`, `gui/results.py`, `gui/window.py`
- **Purpose:** Modern native UI: dashboard (total size prominent), provider cards, Clean All (destructive, with confirmation), per-provider clean, progress, results (before/removed/remaining/cleaned/skipped/errors), rescan, About. States: scanning/ready/cleaning/finished/partial/fatal.
- **Changes:** `Adw.Application` + CSS theme; threaded scan/clean with `GLib.idle_add`; cancel button; conditional-approval checkboxes; results card auto-shown; automatic post-clean rescan; About window.
- **Tests:** py_compile (all 5 modules) → OK; headless runtime test in Task 33.
- **Errors:** Removed a hacky Gdk import and simplified results-child clearing before commit.
- **Resolution:** clean imports.
- **Result:** compiled.
- **Git commit:** `task: add GTK4/libadwaita GUI (app, window, provider rows, results panel)`
- **Next task:** `tests/gui_smoke.py` + run under Xvfb.

## Task 33 — Headless GUI smoke test
- **Task:** Boot the real GUI under Xvfb against a synthetic home and verify dashboard/list populate.
- **File:** `tests/gui_smoke.py`
- **Purpose:** "UI works" must be tested, not assumed (rule 25) — despite no physical display.
- **Changes:** Smoke script: fixture home → real app.run → poll until scan done → assert rows/total/label, pip provider measured exactly 12 345 B.
- **Tests:** `xvfb-run -a /usr/bin/python3 tests/gui_smoke.py` → GUI SMOKE TEST PASS (rc=0, 3 rows, state Ready).
- **Errors:** E-007 (set_application_name), E-008 (Gtk.SimpleAction), E-009 (set_titlebar on Adw window) — all found by this test and fixed.
- **Resolution:** GLib app-name property, Gio.SimpleAction, Adw.ToolbarView.
- **Note:** GTK itself creates ~/.cache/fontconfig during window init — the app legitimately detected it (total 1.3 MiB); assertion therefore checks the exact pip measurement instead of the machine-state-dependent total.
- **Result:** PASS.
- **Git commit:** `task: GUI smoke test passing under Xvfb`
- **Next task:** `data/cachecleaner.desktop` — launcher integration.

## Task 34 — Desktop launcher
- **Task:** `.desktop` file for menu integration (rule 10).
- **File:** `data/cachecleaner.desktop`
- **Purpose:** App must appear in the desktop launcher with icon, categories, keywords.
- **Changes:** Desktop Entry 1.5 with Name/Comment(+de)/Exec/Icon/Categories/Keywords.
- **Tests:** Key-presence check (Type/Name/Exec/Icon/Categories/Terminal) → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add desktop launcher entry`
- **Next task:** icon.

## Task 35 — Application icon
- **Task:** Scalable SVG app icon.
- **File:** `data/icons/hicolor/scalable/apps/cachecleaner.svg`
- **Purpose:** Icon for launcher/About window; hicolor install path.
- **Changes:** Hand-drawn SVG: Adwaita-blue rounded square, cache cylinder, cleaning spark, green safety check.
- **Tests:** XML well-formedness → OK.
- **Errors:** None. **Resolution:** n/a
- **Result:** committed.
- **Git commit:** `task: add scalable application icon`
- **Next task:** `packaging/PKGBUILD`.
