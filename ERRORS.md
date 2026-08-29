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

## E-012 — Version bump broke hard-coded CLI --version test
```
Timestamp: 2026-08-25
Task:    Task 51 — version bump to 0.1.1
File:    tests/test_cli.py
Command: pytest tests/
Error:   test_version asserted literal "0.1.0" → failed after bump to 0.1.1
Root cause: test hard-coded a version string instead of importing __version__
Resolution: import cachecleaner.__version__ and assert on it
Verification: full suite passes
Commit:  task: version test tracks package version dynamically
```

## E-013 — elevation module never committed → v0.1.1 shipped incomplete, app crashed on startup (USER-REPORTED)
```
Timestamp: 2026-08-25 ~20:34 user local time (build/run on EndeavourOS)
Task:    Tasks 44-45 commit sequence
File:    cachecleaner/core/elevation.py, tests/test_elevation.py,
         packaging/cachecleaner-paccache
Command: makepkg -si && cachecleaner   (on the user's machine)
Error:   ImportError: cannot import name 'elevation' from 'cachecleaner.core'
         — the v0.1.1 wheel/tarball contained every module EXCEPT elevation.py
Root cause: WORKFLOW FAILURE, not a code bug. The commit batch for the
         elevation work was aborted by `set -e` when pytest failed during
         that turn; after fixing and re-running the tests only pytest was
         executed — the `git add/commit` lines never ran. Subsequent turns
         used targeted `git add <file>` commits and never ran `git status`,
         so the three files stayed untracked/modified while local tests kept
         passing. v0.1.1 was tagged from that incomplete tree.
Resolution: (1) committed elevation.py, test_elevation.py and the helper
         byte-accounting upgrade; (2) added tests/test_repo_integrity.py —
         the test suite now FAILS if any cachecleaner source file is
         untracked or uncommitted, and imports every module; (3) version
         bumped to 0.1.2 and the release archive verified by downloading it
         and checking for elevation.py + FREED_BYTES helper output.
Verification: full suite 155 passed / 1 skipped; v0.1.2 tarball content
         check (this release step)
Commit:  task: COMMIT the polkit elevation module (was untracked, E-013) +
         follow-up 0.1.2 commits
```

## E-014 — Mixed-safety providers displayed a total the Clean button could not free (USER-REPORTED)
```
Timestamp: 2026-08-26 (user machine: Cargo row showed 311.0 MiB; clicking Clean
         re-scanned to the same value; fontcache 0 B rows looked 'broken')
Task:    Tasks 64-68 — honest size breakdown
File:    cachecleaner/core/provider.py, core/engine.py, gui/provider_row.py,
         gui/window.py
Command: GUI: click Clean on Cargo
Error:   Cargo row total (311 MiB) = SAFE registry/cache + CONDITIONAL
         registry/src; plain Clean removed only the SAFE share and silently
         skipped src → post-clean rescan showed ~the same size; user perceived
         'cleaning does nothing'
Root cause: UI presented one undifferentiated total while clean() correctly
         required approval for the conditional share — a transparency bug,
         not a deletion bug (deletion behaved exactly as the safety model
         mandates)
Resolution: calculate_size() records (safe, conditional, protected) bytes;
         ProviderScan exposes eligible_bytes/conditional_bytes; rows with a
         conditional share show 'X cleanable now · Y needs approval' plus an
         Include checkbox; per-provider Clean opens a three-choice dialog
         (Cancel / Clean regenerable / Clean all)
Verification: reproduced pre-fix (50k freed of 350k, 300k silently remained);
         post-fix tests assert breakdown fields and dialog-level semantics;
         full suite + GUI smoke
Commit:  E-014 commit series
```

## E-015 — Near-miss: pinned sha256 of GitHub's not-yet-generated archive error page
```
Timestamp: 2026-08-26
Task:    v0.1.4 release sha pinning
File:    packaging/PKGBUILD
Command: curl tag tarball immediately after git push of the tag
Error:   Downloaded body was an error page (archive generation lag ~10-30 s);
         its sha256 was written into the PKGBUILD; a naive flow would have
         committed a checksum that could never validate
Root cause: GitHub generates tag archives lazily; first GET returns 404/JSON
Resolution: magic-byte (1f8b) verification loop before hashing; re-downloaded
         the real archive; set -e + pipeline failure stopped the bad commit
Verification: pinned sha a34a3f47… matches the magic-byte-verified real
         archive (correct top dir + E-014 code present). NOTE: subsequent
         re-downloads from this sandbox returned GitHub's 'Forbidden' HTML
         error page (sha 31efc27e…, magic 0d0a) because the sandbox IP got
         rate-limited on codeload — that page, not the archive, caused the
         transient 'mismatch' reading. Users downloading normally get the
         real archive whose sha equals the pinned one.
Commit:  task: pin real sha256 of the v0.1.4 release tarball
```

## E-016 — Clean All silently excludes approval-requiring data; looked like 'does nothing' (USER-REPORTED)
```
Timestamp: 2026-08-26 (user machine, v0.1.4; Clean All freed ~0 of the 311 MiB
         Cargo total because the bulk is conditional registry/src)
Task:    Task 69 — transparency fixes
File:    cachecleaner/gui/window.py, cachecleaner/core/log.py
Error:   user perception: 'it still doesnt clean' — Clean All behaved per spec
         (conditional data needs approval) but the confirmation dialog did not
         say which providers/bytes were being left out; console log also hid
         the freed= numbers (only the file log had them)
Root cause: UX transparency gap on top of the E-014 classification model
Resolution: Clean All dialog now lists every excluded provider with its
         conditional byte count ('Not included without approval: Cargo
         (300 MiB). Tick Include…'); console formatter now emits the same
         key=value fields as the file log
Verification: GUI smoke + full suite; user-side CLI ground-truth command
         provided (clean --json --providers lang.cargo --include-conditional)
Commit:  E-016 series (0.1.5)
```

## E-017 — /var/cache/debtap (~1 GiB) not identified or cleaned (USER-REPORTED)
```
Timestamp: 2026-08-26 (user's Filelight screenshot: /var/cache/debtap 1.2 GiB)
Task:    Tasks 72-78 — debtap provider (maintenance release 0.1.6)
File:    packaging/cachecleaner-paccache, cachecleaner/core/elevation.py,
         cachecleaner/providers/pkgman.py, providers/__init__.py
Error:   no provider modeled debtap; app correctly refused to sweep unknown
         /var/cache entries (safety rule), so the 1.2 GiB stayed untouched
Root cause: coverage gap, not a defect — system caches are DO_NOT_DELETE until
         explicitly modeled, classified and allowlisted in the helper
Resolution: DebtapProvider (CONDITIONAL_CACHE) on a new SystemCacheProvider
         base; helper now takes a NAMED target from a hard internal allowlist
         (pacman|debtap) — arbitrary paths still impossible; polkit flow reused;
         verified live in sandbox (1.1 MiB freed, REMAINING 0, bad target rc=2)
Verification: helper live tests; debtap provider matrix; elevation argv
         contract [pkexec, helper, TARGET, KEEP]; full suite; GUI smoke
Commit:  E-017 series (0.1.6)
```
