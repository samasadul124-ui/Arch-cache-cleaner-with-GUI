"""Tests for streaming size measurement and deletion (rule 4, 15 fixtures).

Everything runs inside tmp_path; the real home directory is never touched.
"""

from __future__ import annotations

import os
import threading

import pytest

from cachecleaner.core.errors import ErrorKind
from cachecleaner.core.fs import delete_contents, dir_size
from cachecleaner.core.safety import PathSafety


def _mk_tree(root, spec: dict):
    """spec: name -> int(size) | dict(subtree) | 'link:target' | 'broken'"""
    root.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, value in spec.items():
        p = root / name
        if isinstance(value, dict):
            total += _mk_tree(p, value)
        elif isinstance(value, str) and value.startswith("link:"):
            os.symlink(value[5:], p)
        elif value == "broken":
            os.symlink(root / "does-not-exist-target", p)
        else:
            p.write_bytes(b"x" * int(value))
            total += int(value)
    return total


@pytest.fixture()
def safety(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    return PathSafety(home=str(tmp_path), allowed_roots=[str(root)]), root


class TestDirSize:
    def test_empty(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        r = dir_size(d)
        assert r.bytes == 0 and r.files == 0

    def test_missing_dir(self, tmp_path):
        r = dir_size(tmp_path / "nope")
        assert r.bytes == 0
        assert any(rec.kind is ErrorKind.PATH_VANISHED for rec in r.errors.records)

    def test_small_exact(self, tmp_path):
        d = tmp_path / "c"
        made = _mk_tree(d, {"a": 100, "b": 250, "sub": {"c": 50}})
        r = dir_size(d)
        assert r.bytes == made == 400
        assert r.files == 3 and r.dirs == 1

    def test_huge_tree(self, tmp_path):
        d = tmp_path / "big"
        spec = {f"dir{i:03}": {f"f{j:02}": 1024 for j in range(40)} for i in range(25)}
        made = _mk_tree(d, spec)  # 25*40 = 1000 files, 1 MiB
        r = dir_size(d)
        assert r.bytes == made
        assert r.files == 1000

    def test_symlink_target_not_counted(self, tmp_path):
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"y" * 10_000)
        d = tmp_path / "c"
        d.mkdir()
        os.symlink(outside, d / "link.bin")
        (d / "real.bin").write_bytes(b"z" * 7)
        r = dir_size(d)
        assert r.bytes < 7 + 100          # link target NOT counted
        assert r.symlinks == 1

    def test_broken_symlink_ok(self, tmp_path):
        d = tmp_path / "c"
        _mk_tree(d, {"broken": "broken"})
        r = dir_size(d)  # must not raise
        assert r.symlinks == 1

    def test_permission_denied_subtree(self, tmp_path):
        d = tmp_path / "c"
        _mk_tree(d, {"open": 10, "locked": {"secret": 999}})
        os.chmod(d / "locked", 0)
        try:
            r = dir_size(d)
            assert r.bytes >= 10  # readable part still measured
            kinds = {rec.kind for rec in r.errors.records}
            assert ErrorKind.PERMISSION_DENIED in kinds
        finally:
            os.chmod(d / "locked", 0o755)

    def test_file_vanishing_during_scan(self, tmp_path, monkeypatch):
        d = tmp_path / "c"
        _mk_tree(d, {"a": 10, "b": 20})
        real_scandir = os.scandir

        def flaky_scandir(p):
            # remove one file right as the scan starts -> entry disappears
            victim = d / "b"
            if victim.exists():
                victim.unlink()
            return real_scandir(p)

        monkeypatch.setattr("cachecleaner.core.fs.os.scandir", flaky_scandir)
        r = dir_size(d)  # must not raise
        assert r.bytes >= 10


class TestDeleteContents:
    def test_basic_delete_keeps_root(self, safety):
        s, root = safety
        made = _mk_tree(root, {"a": 100, "sub": {"b": 300, "deep": {"c": 50}}})
        r = delete_contents(root, s)
        assert r.bytes_freed == made
        assert r.files_deleted == 3 and r.dirs_deleted == 2
        assert root.is_dir() and list(root.iterdir()) == []

    def test_dry_run_touches_nothing(self, safety):
        s, root = safety
        made = _mk_tree(root, {"a": 100, "sub": {"b": 200}})
        r = delete_contents(root, s, dry_run=True)
        assert r.bytes_freed == made and r.files_deleted == 2
        assert (root / "a").exists() and (root / "sub" / "b").exists()

    def test_refuses_outside_root(self, tmp_path):
        s = PathSafety(home=str(tmp_path), allowed_roots=[str(tmp_path / "cache")])
        victim = tmp_path / "victim"
        _mk_tree(victim, {"a": 10})
        r = delete_contents(victim, s)
        assert r.refused and (victim / "a").exists()
        assert r.errors.records[0].kind is ErrorKind.INVALID_PATH

    def test_refuses_dangerous_paths(self, safety):
        s, _ = safety
        for p in ("/", "/home", os.environ.get("HOME", "/root"), ""):
            r = delete_contents(p, s)
            assert r.refused, p

    def test_symlink_outside_is_unlinked_not_followed(self, safety, tmp_path):
        s, root = safety
        outside_dir = tmp_path / "precious"
        _mk_tree(outside_dir, {"keep": 5})
        os.symlink(outside_dir, root / "escape")
        r = delete_contents(root, s)
        assert r.links_deleted == 1
        assert not (root / "escape").exists()
        assert (outside_dir / "keep").exists()     # target untouched

    def test_broken_symlink_removed(self, safety):
        s, root = safety
        _mk_tree(root, {"broken": "broken"})
        r = delete_contents(root, s)
        assert r.links_deleted == 1 and not (root / "broken").exists()

    def test_permission_denied_recorded_not_fatal(self, safety):
        s, root = safety
        _mk_tree(root, {"ok": 10, "locked": {"inner": 99}})
        os.chmod(root / "locked", 0o500)
        try:
            r = delete_contents(root, s)
            assert (root / "ok").exists() is False
            assert len(r.errors) >= 1
            kinds = {rec.kind for rec in r.errors.records}
            assert ErrorKind.PERMISSION_DENIED in kinds
        finally:
            os.chmod(root / "locked", 0o755)

    def test_cache_recreated_during_cleanup(self, safety):
        """An app recreating cache files mid-clean must not crash the run."""
        s, root = safety
        _mk_tree(root, {"a": 10})
        real_unlink = os.unlink
        recreated = {"done": False}

        def sneaky_unlink(p):
            real_unlink(p)
            if not recreated["done"]:
                recreated["done"] = True
                (root / "recreated-by-app.tmp").write_bytes(b"n" * 64)

        import cachecleaner.core.fs as fs_mod
        orig = fs_mod.os.unlink
        fs_mod.os.unlink = sneaky_unlink
        try:
            r = delete_contents(root, s)
        finally:
            fs_mod.os.unlink = orig
        assert not r.cancelled
        # recreated file survived this pass — that's exactly why the engine
        # does a *fresh rescan* afterwards instead of trusting arithmetic
        assert (root / "recreated-by-app.tmp").exists() or r.files_deleted >= 1

    def test_cancellation(self, safety):
        s, root = safety
        _mk_tree(root, {f"f{i:02}": 10 for i in range(50)})
        cancel = threading.Event()

        def prog(n, b):
            if n >= 3:
                cancel.set()

        r = delete_contents(root, s, cancel=cancel, progress=prog, progress_every=1)
        assert r.cancelled
        assert list(root.iterdir())          # some work left, as expected
        assert r.files_deleted < 50

    def test_progress_reports(self, safety):
        s, root = safety
        _mk_tree(root, {f"f{i}": 1 for i in range(3)})
        seen = []
        delete_contents(root, s, progress=lambda n, b: seen.append((n, b)))
        assert seen and seen[-1][0] == 3

    def test_missing_root(self, safety):
        s, root = safety
        r = delete_contents(root / "ghost", s)
        # ghost is inside allowed root but absent -> refused as vanished
        assert r.refused
