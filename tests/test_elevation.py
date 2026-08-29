"""Tests for the polkit elevation layer (E-011).

A fake pkexec shell script stands in for the real polkit flow — the tests
exercise exit-code classification, output parsing and user messages without
ever touching real authentication.
"""

from __future__ import annotations

import os
import stat

import pytest

from cachecleaner.core.elevation import (
    ElevationResult,
    ElevationStatus,
    run_paccache,
)


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/bin/bash\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(p)


@pytest.fixture()
def helper(tmp_path):
    return _write(tmp_path, "fake-helper",
                  'echo "FREED_BYTES=1234"\n'
                  'echo "REMAINING_BYTES=0"\n'
                  'echo "pacman cache: freed 1 KiB (kept 0 newest per package)"\n')


class TestSuccess:
    def test_success_parses_bytes(self, tmp_path, helper):
        pk = _write(tmp_path, "pkexec", '"$@"\n')   # passthrough: run helper
        r = run_paccache(keep=0, pkexec=pk, helper=helper)
        assert r.ok
        assert r.freed_bytes == 1234
        assert r.remaining_bytes == 0
        assert "successfully" in r.user_message()

    def test_success_with_remaining_keep(self, tmp_path):
        h = _write(tmp_path, "h", 'echo "FREED_BYTES=10"\necho "REMAINING_BYTES=90"\n')
        pk = _write(tmp_path, "pkexec", '"$@"\n')
        r = run_paccache(pkexec=pk, helper=h)
        assert r.ok and r.remaining_bytes == 90


class TestAuthFlow:
    def test_dismissed_is_cancelled(self, tmp_path, helper):
        pk = _write(tmp_path, "pkexec",
                    'echo "Error executing command as user: Dismissed" >&2\nexit 126\n')
        r = run_paccache(pkexec=pk, helper=helper)
        assert r.status is ElevationStatus.CANCELLED
        assert r.user_message() == "Pacman cache cleanup cancelled."
        assert r.freed_bytes is None          # nothing was modified

    def test_denied_is_auth_failed(self, tmp_path, helper):
        pk = _write(tmp_path, "pkexec",
                    'echo "Authentication failed" >&2\nexit 126\n')
        r = run_paccache(pkexec=pk, helper=helper)
        assert r.status is ElevationStatus.AUTH_FAILED
        assert "was not modified" in r.user_message()

    def test_helper_error_propagates(self, tmp_path):
        h = _write(tmp_path, "h", 'echo "ERROR=fs" >&2\nexit 1\n')
        pk = _write(tmp_path, "pkexec", '"$@"\n')   # passthrough
        r = run_paccache(pkexec=pk, helper=h)
        assert r.status is ElevationStatus.HELPER_ERROR
        assert "ERROR=fs" in r.detail


class TestFailures:
    def test_missing_helper(self, tmp_path):
        # realistic pkexec: it execs the helper, so a missing helper errors
        pk = _write(tmp_path, "pkexec", 'shift 0; "$@" || exit 127\n')
        r = run_paccache(pkexec=pk, helper="/nonexistent/helper-xyz")
        assert r.status is ElevationStatus.HELPER_ERROR

    def test_helper_none_and_not_installed(self, tmp_path, monkeypatch):
        import cachecleaner.core.elevation as el
        monkeypatch.setattr(el, "_HELPER_CANDIDATES", ("/nonexistent/a",))
        monkeypatch.setattr(el.shutil, "which", lambda _x: None)
        pk = _write(tmp_path, "pkexec", 'exit 0\n')
        r = run_paccache(pkexec=pk, helper=None)
        assert r.status is ElevationStatus.HELPER_MISSING

    def test_pkexec_missing(self, tmp_path, helper, monkeypatch):
        monkeypatch.setattr("cachecleaner.core.elevation.shutil.which",
                            lambda _x: None)
        r = run_paccache(pkexec="pkexec-definitely-absent", helper=helper)
        assert r.status is ElevationStatus.LAUNCH_ERROR
        assert "polkit" in r.detail


class TestSecurityContract:
    def test_no_password_arguments(self, tmp_path, helper):
        """The command line must only be [pkexec, helper, KEEP] — nothing else."""
        seen = {}
        pk = _write(tmp_path, "pkexec", 'printf "%s\\n" "$@" > /dev/null\nexit 0\n')
        import subprocess as sp
        real_run = sp.run

        def spy(cmd, **kw):
            seen["cmd"] = cmd
            return real_run(cmd, **kw)

        import cachecleaner.core.elevation as el
        orig = el.subprocess.run
        el.subprocess.run = spy
        try:
            run_paccache(keep=0, pkexec=pk, helper=helper)
        finally:
            el.subprocess.run = orig
        cmd = seen["cmd"]
        # minimal argv: [pkexec, helper, TARGET, KEEP] — no secrets, no paths
        assert len(cmd) == 4
        assert cmd[2] == "pacman" and cmd[3] == "0"
        assert all(not c.startswith("-") and not c.startswith("/") or i < 2
                   for i, c in enumerate(cmd))
