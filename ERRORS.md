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
