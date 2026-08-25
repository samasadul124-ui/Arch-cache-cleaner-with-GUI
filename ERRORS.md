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
