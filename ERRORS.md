# ERRORS — cache-cleaner

Every error encountered during development is recorded here and never erased,
even after it is fixed. Format per entry:

```
Timestamp:
Task:
File:
Command:
Error:
Root cause:
Resolution:
Verification:
Commit:
```

---

## E-001 — Bootstrap shell invocation failed (cwd did not exist)
```
Timestamp: 2026-08-25 ~06:20 UTC
Task:    Task 1 — Repository bootstrap
File:    (none — shell invocation itself)
Command: bash bootstrap script with cwd=/home/user/cache-cleaner
Error:   shell_error (exit_code=null) after 123 ms, no output — sandbox could not
         enter the working directory
Root cause: The tool call specified a working directory that had not been created yet;
         the sandbox aborts before executing the script when cwd is missing.
Resolution: Re-ran the identical bootstrap with cwd=/home/user and `mkdir -p` inside
         the script.
Verification: Re-run completed; commit 9cf57d9 created and pushed to origin/main.
Commit:  (recorded in this commit)
```

## E-002 — detect() noise: providers detected via binary presence without any cache
```
Timestamp: 2026-08-25 ~07:05 UTC
Task:    Task 22 — provider tests
File:    cachecleaner/providers/langtools.py, cachecleaner/providers/pkgman.py
Command: pytest tests/test_providers.py::TestDetectionOnFixture::test_no_cache_detected
Error:   assert detect_all(ctx) == [] failed — NpmProvider/PipProvider detected via
         which() fallback although fixture home contained no caches
Root cause: detect() treated "tool installed" as "cache present", producing
         0-byte noise providers and breaking empty-fixture expectations
Resolution: detect() now requires the cache directory to exist; installed-but-
         cacheless tools stay hidden (documented in code)
Verification: test_no_cache_detected passes; full suite green
Commit:  task: fix provider detection isolation (ctx.home anchor, dir-based detect)
```

## E-003 — Provider path anchored on env $HOME instead of ProviderContext
```
Timestamp: 2026-08-25 ~07:08 UTC
Task:    Task 22 — provider tests
File:    cachecleaner/providers/langtools.py
Command: pytest tests/test_providers.py::TestDetectionOnFixture::test_layered_detection
Error:   lang.pip not detected in fixture — path resolved to the REAL $HOME
Root cause: _SimpleProvider._path() used ctx.expand("~/...") → expanduser reads
         the process env HOME, ignoring ctx.home (isolation leak)
Resolution: anchor on ctx.home: os.path.join(self.ctx.home, relpath)
Verification: layered detection test passes; full suite 105 green
Commit:  task: fix provider detection isolation (ctx.home anchor, dir-based detect)
```

## E-004 — Provider clean refused when cache root not in safety allowlist (by design)
```
Timestamp: 2026-08-25 ~07:02 UTC
Task:    Task 22 — provider tests
File:    tests/test_providers.py (fixture), engine design
Command: pytest TestFirefoxSafety::test_clean_keeps_profile_data
Error:   bytes_freed == 0 — delete_contents refused ~/.mozilla/.../cache2
Root cause: PathSafety correctly refused a path outside the fixture allowlist;
         production engine must register provider-declared cache paths as
         allowed roots before cleaning
Resolution: test registers the exact cache2 root (as the engine will); engine
         requirement recorded in ARCHITECTURE §7 and will be implemented in
         core/engine.py
Verification: test passes with explicit allowlist; refusal path itself proven correct
Commit:  task: add provider safety and detection tests
```

## E-005 — Dry-run reported 0 B "removed" because rescan saw untouched files
```
Timestamp: 2026-08-25 ~07:30 UTC
Task:    Task 25 — engine tests
File:    cachecleaner/core/engine.py
Command: pytest tests/test_engine.py::TestClean::test_dry_run_deletes_nothing
Error:   assert out.removed_bytes >= 101_000 failed (was 0)
Root cause: removed_bytes used before−after rescan even in dry-run; since a
         dry-run deletes nothing, the fresh scan equals 'before' → 0
Resolution: removed_bytes property returns the planned sum (per-provider
         traversal counts) when dry_run=True or no rescan ran; real cleans
         still use the two-measurement rule
Verification: dry-run test passes; real-clean semantics unchanged (tests green)
Commit:  task: implement cleaning engine with fresh-rescan verification
```

## E-006 — Engine test re-created cache too early (test-design flaw)
```
Timestamp: 2026-08-25 ~07:28 UTC
Task:    Task 25 — engine tests
File:    tests/test_engine.py
Command: pytest tests/test_engine.py::TestClean::test_cache_recreated_during_cleanup_is_seen_by_rescan
Error:   after_bytes was 0 instead of 7_000
Root cause: the test recreated the cache file at the first deletion, i.e.
         BEFORE the dynamic provider's turn — so it was legitimately deleted
         by that later provider; only recreation AFTER all cleans exercises
         rule 6 correctly
Resolution: rewrite: recreate the file in the progress callback at the
         'Re-measuring remaining cache…' phase, just before the fresh scan
Verification: test now asserts measured after_bytes == 7_000; passes
Commit:  task: add engine integration tests (12 scenarios)
```

## E-007 — Adw.Application has no set_application_name/set_version
```
Timestamp: 2026-08-25 ~06:55 UTC
Task:    Task 33 — GUI smoke test
File:    cachecleaner/gui/app.py
Command: xvfb-run -a python3 tests/gui_smoke.py
Error:   AttributeError: 'CacheCleanerApp' object has no attribute 'set_application_name'
Root cause: those setters belong to Gtk.AboutDialog, not Gio.Application;
         app-level name is a GLib process property
Resolution: GLib.set_application_name(APP_NAME); version passed directly to
         Adw.AboutWindow; unused __version__ import dropped
Verification: smoke test progressed past app construction
Commit:  task: fix GUI API issues found by headless smoke test
```

## E-008 — Gtk.SimpleAction does not exist
```
Timestamp: 2026-08-25 ~06:56 UTC
Task:    Task 33 — GUI smoke test
File:    cachecleaner/gui/window.py
Command: xvfb-run -a python3 tests/gui_smoke.py
Error:   AttributeError: 'gi.repository.Gtk' object has no attribute 'SimpleAction'
Root cause: actions live in Gio, not Gtk
Resolution: Gio.SimpleAction.new("about", None)
Verification: window construction passed; smoke test progressed
Commit:  task: fix GUI API issues found by headless smoke test
```

## E-009 — gtk_window_set_titlebar unsupported on AdwApplicationWindow
```
Timestamp: 2026-08-25 ~06:57 UTC
Task:    Task 33 — GUI smoke test
File:    cachecleaner/gui/window.py
Command: xvfb-run -a python3 tests/gui_smoke.py
Error:   Adwaita-ERROR: gtk_window_set_titlebar() is not supported for
         AdwApplicationWindow → trap
Root cause: libadwaita windows use Adw.ToolbarView for header bars
Resolution: Adw.ToolbarView with add_top_bar(header) and scrolled content via
         set_content; window.set_content(toolbar_view)
Verification: GUI smoke test now boots fully: 3 rows rendered, scan 'Ready',
         pip provider measured exactly 12_345 B
Commit:  task: fix GUI API issues found by headless smoke test
```

## E-010 — PKGBUILD source-directory mismatch breaks fresh makepkg build (USER-REPORTED)
```
Timestamp: 2026-08-25 (reported by user after install attempt on EndeavourOS)
Task:    Task 41 — PKGBUILD fix
File:    packaging/PKGBUILD
Command: cd cache-cleaner/packaging && makepkg -si   (on EndeavourOS, Python 3.14)
Error:   build() aborted: 'cd: cachecleaner-0.1.0: No such file or directory'
Root cause: build()/package() used `cd "$pkgname-$pkgver"` with pkgname=cachecleaner,
         but GitHub tag archives extract to <REPO>-<version> = cache-cleaner-0.1.0
         (repo name has a hyphen; package name does not). Arch package name was
         implicitly coupled to the upstream archive's directory name.
Resolution: decouple: keep pkgname=cachecleaner; introduce _srcrepo=cache-cleaner
         and `cd "$srcdir/$_srcrepo-$pkgver"` in build()/package(); source URL
         renamed accordingly. Added provides/conflicts for the user's manually
         renamed cache-cleaner package so pacman upgrades cleanly.
Verification: tests/test_packaging.py asserts the cd-target matches the GitHub
         extraction convention and all installed files exist; bash -n passes.
         (makepkg itself cannot run in this Debian sandbox — user re-build
         confirms; acceptance criteria quoted in the report.)
Commit:  task: fix PKGBUILD source-directory coupling (E-010)
```

## E-011 — Pacman cache never cleaned: privilege escalation not wired (USER-REPORTED)
```
Timestamp: 2026-08-25 (reported by user after install on EndeavourOS)
Task:    Tasks 43-49 — elevation wiring
File:    cachecleaner/core/engine.py, providers/pkgman.py, gui/window.py, gui/provider_row.py
Command: n/a (GUI workflow)
Error:   Pacman cache provider was detected and measured, but cleaning it only
         produced an INSUFFICIENT_PRIVILEGES skip — the app never triggered
         polkit authentication, so /var/cache/pacman/pkg was never cleaned.
Root cause: engine.clean() pre-skipped every provider flagged needs_elevation;
         the existing cachecleaner-paccache helper + polkit policy were shipped
         but never invoked by the application.
Resolution: new core/elevation.py runs `pkexec /usr/bin/cachecleaner-paccache`
         (polkit handles the password — the app never sees/stores it);
         PacmanCacheProvider.clean() performs elevation, then re-measures the
         directory and reports measured before/removed/after; cancelled (pkexec
         rc 126 dismissed) vs authentication-failed are classified and surfaced;
         GUI enables the pacman Clean button and the approval checkbox; engine no
         longer pre-skips elevation providers.
Verification: tests/test_elevation.py (fake pkexec: success/cancel/denied/helper
         error), tests/test_providers.py pacman matrix, live sandbox re-test of
         the helper, full suite + Xvfb GUI smoke.
Commit:  tasks 43-49 series (see TASK_LOG)
```
