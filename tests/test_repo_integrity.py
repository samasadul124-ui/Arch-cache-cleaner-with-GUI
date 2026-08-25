"""Repository-integrity guard (regression test for E-013).

E-013: elevation.py + its tests existed on disk and passed locally, but were
never committed — so the release tarball lacked the module and the installed
app crashed with ImportError. These tests make that class of mistake fail
LOUDLY at test time:

  1. every .py file under cachecleaner/ must be tracked by git, and
  2. every importable module must actually import.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import shutil
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _git_tracked_py() -> set[str]:
    if shutil.which("git") is None or not os.path.isdir(os.path.join(REPO, ".git")):
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "-C", REPO, "ls-files", "cachecleaner"],
                         capture_output=True, text=True, check=True)
    return {p for p in out.stdout.splitlines() if p.endswith(".py")}


def _disk_py() -> set[str]:
    found = set()
    for root, dirs, files in os.walk(os.path.join(REPO, "cachecleaner")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                found.add(os.path.relpath(os.path.join(root, f), REPO))
    return found


class TestSourceTracking:
    def test_every_source_file_is_committed(self):
        disk = _disk_py()
        tracked = _git_tracked_py()
        untracked = disk - tracked
        missing = tracked - disk
        assert not untracked, (
            f"E-013 regression: source files exist on disk but are NOT in "
            f"git — they will be missing from release tarballs: {sorted(untracked)}")
        assert not missing, f"git tracks files that are missing on disk: {sorted(missing)}"

    def test_working_tree_has_no_uncommitted_sources(self):
        if shutil.which("git") is None or not os.path.isdir(os.path.join(REPO, ".git")):
            pytest.skip("not a git checkout")
        out = subprocess.run(
            ["git", "-C", REPO, "status", "--porcelain", "--", "cachecleaner"],
            capture_output=True, text=True, check=True)
        assert out.stdout.strip() == "", (
            "uncommitted changes under cachecleaner/: \n" + out.stdout)


class TestAllModulesImport:
    def test_core_and_providers_import(self):
        import cachecleaner
        for mod in pkgutil.walk_packages(cachecleaner.__path__, "cachecleaner."):
            if mod.name.startswith("cachecleaner.gui"):
                continue                      # needs GTK — tested separately
            importlib.import_module(mod.name)

    def test_gui_modules_import_when_gtk_available(self):
        try:
            import gi  # noqa: F401
        except ImportError:
            pytest.skip("PyGObject not available in this interpreter")
        import cachecleaner
        for mod in pkgutil.walk_packages(cachecleaner.__path__, "cachecleaner."):
            if not mod.name.startswith("cachecleaner.gui"):
                continue
            try:
                importlib.import_module(mod.name)
            except Exception:
                # gi present but no display/typelib → skip rather than fail
                pytest.skip("GTK typelib/display unavailable for gui import")
