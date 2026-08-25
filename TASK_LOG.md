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
