"""Integration tests for the cleaning engine (rules 5, 6, 14, 15).

A fully synthetic $HOME inside tmp_path is used — never the real one.
"""

from __future__ import annotations

import os
import threading

import pytest

from cachecleaner.core.engine import Engine
from cachecleaner.core.errors import ErrorKind
from cachecleaner.core.provider import CacheProvider, Category, CachePath
from cachecleaner.core.safety import SafetyLevel


def _w(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * n)
    return n


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home" / "user"
    cache = home / ".cache"
    (cache / "pip").mkdir(parents=True)
    (cache / "thumbnails" / "large").mkdir(parents=True)
    (cache / "someapp").mkdir(parents=True)
    _w(str(cache / "pip" / "wheel1.whl"), 40_000)
    _w(str(cache / "thumbnails" / "large" / "img.png"), 60_000)
    _w(str(cache / "someapp" / "data.cache"), 1_000)
    for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(home))
    return home


class TestScan:
    def test_total_matches_fixture(self, fake_home):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        assert rep.total_bytes == 101_000
        ids = {s.provider.id for s in rep.scans}
        assert {"lang.pip", "xdg.thumbnails", "xdg.other"} <= ids
        # 'someapp' is unclaimed -> belongs to the dynamic provider
        other = rep.by_id("xdg.other")
        assert other.size_bytes == 1_000

    def test_no_cache_detected(self, tmp_path, monkeypatch):
        home = tmp_path / "bare"
        (home / ".cache").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            monkeypatch.delenv(var, raising=False)
        eng = Engine(home=str(home))
        rep = eng.scan()
        assert rep.total_bytes == 0

    def test_progress_callback(self, fake_home):
        eng = Engine(home=str(fake_home))
        seen = []
        eng.scan(progress=lambda f, m: seen.append(f))
        assert seen and seen[-1] == pytest.approx(1.0)


class TestClean:
    def test_full_clean_and_fresh_rescan(self, fake_home):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        out = eng.clean(rep)
        assert out.before_bytes == 101_000
        assert out.after_bytes == 0                 # fresh scan, not arithmetic
        assert out.removed_bytes == 101_000
        assert len(out.cleaned) >= 3 and not out.failed and out.ok

    def test_dry_run_deletes_nothing(self, fake_home):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        out = eng.clean(rep, dry_run=True)
        assert out.removed_bytes >= 101_000  # plan says would-remove
        assert (fake_home / ".cache" / "pip" / "wheel1.whl").exists()

    def test_cache_recreated_during_cleanup_is_seen_by_rescan(self, fake_home):
        """Rule 6: an app writing cache during cleanup shows up in 'remaining'."""
        eng = Engine(home=str(fake_home))
        rep = eng.scan()

        # an app recreates its cache right before the post-clean rescan
        def late_writer(frac, msg):
            if "Re-measuring" in msg:
                _w(str(fake_home / ".cache" / "someapp" / "reborn.cache"), 7_000)

        out = eng.clean(rep, progress=late_writer)
        assert out.after_bytes == 7_000             # measured, not computed
        assert out.removed_bytes == 101_000 - 7_000

    def test_per_provider_selection(self, fake_home):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        out = eng.clean(rep, provider_ids={"lang.pip"})
        assert (fake_home / ".cache" / "thumbnails" / "large" / "img.png").exists()
        assert not (fake_home / ".cache" / "pip" / "wheel1.whl").exists()

    def test_cancellation(self, fake_home):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        cancel = threading.Event()
        cancel.set()
        out = eng.clean(rep, cancel=cancel)
        assert out.cancelled
        assert (fake_home / ".cache" / "pip" / "wheel1.whl").exists()

    def test_failing_provider_does_not_stop_others(self, fake_home, monkeypatch):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()

        class Boom(CacheProvider):
            id, name, category = "test.boom", "Boom", Category.APPLICATION
            def detect(self): return True
            def cache_paths(self): return []
            def clean(self, **kw): raise RuntimeError("provider exploded")

        boom = Boom(eng.ctx)
        rep.scans.insert(0, rep.by_id("lang.pip").__class__(provider=boom))
        out = eng.clean(rep)
        assert any(r.provider_id == "test.boom" and len(r.errors)
                   for r in out.per_provider)
        assert any(r.provider_id == "xdg.thumbnails" and r.cleaned_paths
                   for r in out.per_provider)      # others still cleaned

    def test_conditional_requires_approval(self, fake_home):
        ccache = fake_home / ".cache" / "ccache"
        _w(str(ccache / "obj.o"), 5_000)
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        out = eng.clean(rep, provider_ids={"lang.ccache"})
        assert (ccache / "obj.o").exists()          # untouched without approval
        assert out.per_provider[0].skipped_paths == 1
        out2 = eng.clean(eng.scan(), provider_ids={"lang.ccache"},
                         include_conditional={"lang.ccache"})
        assert not (ccache / "obj.o").exists()

    def test_elevation_provider_reported_not_cleaned(self, fake_home, monkeypatch):
        eng = Engine(home=str(fake_home))
        rep = eng.scan()
        # simulate a privileged provider recorded by the scan (e.g. pacman cache)
        s = rep.scans[0]
        s.needs_elevation = True
        out = eng.clean(rep, provider_ids={s.provider.id}, rescan=False)
        r = out.per_provider[0]
        assert r.errors.records[0].kind is ErrorKind.INSUFFICIENT_PRIVILEGES
        assert r.attempted is False

    def test_partial_cleanup_counts(self, fake_home):
        locked = fake_home / ".cache" / "someapp" / "locked"
        os.makedirs(locked)
        _w(str(locked / "f"), 100)
        os.chmod(locked, 0o500)
        try:
            eng = Engine(home=str(fake_home))
            rep = eng.scan()
            out = eng.clean(rep, provider_ids={"xdg.other"})
            assert len(out.failed) == 1             # error surfaced, not hidden
            assert out.errors.records
        finally:
            os.chmod(locked, 0o755)
