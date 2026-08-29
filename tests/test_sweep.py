"""Advanced '*cache*' sweep tests: discovery rules + manual-selection clean."""

from __future__ import annotations

import os

import pytest

from cachecleaner.core import sweep
from cachecleaner.core.engine import Engine
from cachecleaner.providers.sweep import CacheNameSweepProvider


@pytest.fixture()
def fhome(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cache" / "app").mkdir(parents=True)
    (home / "MyCache").mkdir()
    (home / "proj" / "shader-cache").mkdir(parents=True)
    (home / "proj" / "shader-cache" / "seed.bin").write_bytes(b"x" * 500)
    (home / "proj" / "node_modules" / "pkg" / ".cache").mkdir(parents=True)
    (home / ".git" / "cache").mkdir(parents=True)
    (home / "safe" / "docs").mkdir(parents=True)
    # protected data inside a cache-named dir -> must NOT be offered
    (home / "mixed" / "cachestuff" / "tdata").mkdir(parents=True)
    # symlink escape named cache -> neither followed nor listed
    os.symlink("/etc", home / "cache-link")
    for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(home))
    return home


class TestDiscovery:
    def test_finds_cache_named_dirs(self, fhome):
        found = sweep.find_cache_named_dirs(str(fhome))
        rel = {os.path.relpath(p, fhome) for p in found}
        assert ".cache" in rel
        assert "MyCache" in rel
        assert os.path.join("proj", "shader-cache") in rel

    def test_pruned_trees_not_listed(self, fhome):
        found = sweep.find_cache_named_dirs(str(fhome))
        rel = {os.path.relpath(p, fhome) for p in found}
        assert not any(p.startswith(os.path.join("proj", "node_modules"))
                       for p in rel)
        assert not any(p.startswith(".git") for p in rel)

    def test_symlink_escape_neither_followed_nor_listed(self, fhome):
        found = sweep.find_cache_named_dirs(str(fhome))
        assert not any(os.path.basename(p) == "cache-link" for p in found)
        assert not any(p.startswith("/etc") for p in found)

    def test_denied_child_dir_not_offered(self, fhome):
        found = sweep.find_cache_named_dirs(str(fhome))
        assert not any(os.path.basename(p) == "cachestuff" for p in found)

    def test_non_cache_dirs_not_listed(self, fhome):
        found = sweep.find_cache_named_dirs(str(fhome))
        assert not any(os.path.basename(p) == "docs" for p in found)


class TestEngineWiring:
    def test_off_by_default(self, fhome):
        eng = Engine(home=str(fhome))
        assert eng.scan().by_id("advanced.cache-name-sweep") is None

    def test_on_when_advanced(self, fhome):
        eng = Engine(home=str(fhome))
        s = eng.scan(advanced=True).by_id("advanced.cache-name-sweep")
        assert s is not None and s.conditional_bytes > 0


class TestManualSelectionClean:
    def _provider(self, fhome):
        from cachecleaner.core.provider import ProviderContext
        from cachecleaner.core.safety import PathSafety
        ctx = ProviderContext(home=str(fhome), xdg_cache=str(fhome / ".cache"),
                              xdg_config=str(fhome / ".config"),
                              xdg_data=str(fhome / ".local" / "share"),
                              safety=PathSafety(home=str(fhome),
                                                allowed_roots=[str(fhome)]))
        return CacheNameSweepProvider(ctx)

    def test_only_selected_paths_deleted(self, fhome):
        (fhome / "MyCache" / "a.bin").write_bytes(b"x" * 100)
        (fhome / "proj" / "shader-cache" / "b.bin").write_bytes(b"x" * 200)
        p = self._provider(fhome)
        p.selected = {str(fhome / "MyCache")}
        r = p.clean()
        assert r.cleaned_paths == 1 and r.bytes_freed == 100
        assert not (fhome / "MyCache" / "a.bin").exists()
        assert (fhome / "proj" / "shader-cache" / "b.bin").exists()  # untouched

    def test_nothing_deleted_without_selection(self, fhome):
        (fhome / "MyCache" / "a.bin").write_bytes(b"x" * 100)
        p = self._provider(fhome)
        r = p.clean()
        assert r.cleaned_paths == 0 and r.skipped_paths >= 1
        assert (fhome / "MyCache" / "a.bin").exists()

    def test_injected_outside_path_refused(self, fhome):
        p = self._provider(fhome)
        p.selected = {"/etc"}          # outside home → validator rejects
        r = p.clean()
        assert r.cleaned_paths == 0 and len(r.errors) == 1

    def test_non_cache_name_refused_even_if_selected(self, fhome):
        (fhome / "safe" / "docs" / "f").write_bytes(b"x")
        p = self._provider(fhome)
        p.selected = {str(fhome / "safe" / "docs")}
        r = p.clean()
        assert r.cleaned_paths == 0   # never offered AND re-checked on clean
        assert (fhome / "safe" / "docs" / "f").exists()
