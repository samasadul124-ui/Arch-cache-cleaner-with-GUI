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
