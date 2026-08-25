"""Provider-level tests: detection, safety boundaries, cleaning behaviour.

All fixtures live in tmp_path — never against the real home directory.
"""

from __future__ import annotations

import os

import pytest

from cachecleaner.core.provider import ProviderContext
from cachecleaner.core.safety import PathSafety, SafetyLevel
from cachecleaner.providers import PROVIDER_CLASSES, detect_all, instantiate_all
from cachecleaner.providers.browsers import ChromeProvider, FirefoxProvider
from cachecleaner.providers.electron import ElectronAppsProvider, VSCodeProvider


@pytest.fixture()
def fx(tmp_path):
    home = tmp_path / "home"
    cache = home / ".cache"
    cfg = home / ".config"
    cache.mkdir(parents=True)
    cfg.mkdir()
    ctx = ProviderContext(
        home=str(home), xdg_cache=str(cache), xdg_config=str(cfg),
        xdg_data=str(home / ".local" / "share"),
        safety=PathSafety(home=str(home), allowed_roots=[str(cache), str(cfg)]),
    )
    return home, cache, cfg, ctx


class TestRegistry:
    def test_unique_ids(self):
        ids = [cls.id for cls in PROVIDER_CLASSES]
        assert len(ids) == len(set(ids)) and len(ids) >= 25

    def test_every_class_has_required_metadata(self):
        for cls in PROVIDER_CLASSES:
            assert cls.id and cls.name and cls.category, cls


class TestFirefoxSafety:
    def test_only_cache2_is_targeted(self, fx):
        home, cache, cfg, ctx = fx
        prof = home / ".mozilla" / "firefox" / "abc.default-release"
        for sub in ("cache2", "storage", "databases"):
            (prof / sub).mkdir(parents=True)
        (prof / "cookies.sqlite").write_text("cookies")
        (prof / "key4.db").write_text("keys")
        p = FirefoxProvider(ctx)
        assert p.detect()
        paths = [cp.path for cp in p.cache_paths()]
        assert paths == [str(prof / "cache2")]          # nothing else eligible

    def test_clean_keeps_profile_data(self, fx):
        home, cache, cfg, ctx = fx
        prof = home / ".mozilla" / "firefox" / "abc.default"
        c2 = prof / "cache2"
        c2.mkdir(parents=True)
        (c2 / "big.bin").write_bytes(b"x" * 5000)
        (prof / "bookmarks.html").write_text("mine")
        # production engine registers provider-declared paths as allowed roots;
        # emulate that here:
        ctx.safety = PathSafety(home=str(home), allowed_roots=[str(cache), str(cfg), str(c2)])
        p = FirefoxProvider(ctx)
        r = p.clean()
        assert r.bytes_freed == 5000
        assert (prof / "bookmarks.html").exists()
        assert not (c2 / "big.bin").exists()


class TestChromiumSafety:
    def test_profile_data_never_listed(self, fx):
        home, cache, cfg, ctx = fx
        prof = cfg / "google-chrome" / "Default"
        for sub in ("Cache", "Code Cache", "GPUCache",
                    "Local Storage", "IndexedDB", "databases"):
            (prof / sub).mkdir(parents=True)
        (prof / "Login Data").write_text("creds")
        p = ChromeProvider(ctx)
        paths = {os.path.basename(cp.path) for cp in p.cache_paths()}
        assert paths == {"Cache", "Code Cache", "GPUCache"}

    def test_clean_frees_cache_only(self, fx):
        home, cache, cfg, ctx = fx
        prof = cfg / "google-chrome" / "Default"
        (prof / "Cache").mkdir(parents=True)
        (prof / "Cache" / "data_1").write_bytes(b"c" * 1234)
        (prof / "Local Storage").mkdir()
        (prof / "Local Storage" / "leveldb").write_bytes(b"l" * 99)
        p = ChromeProvider(ctx)
        r = p.clean()
        assert r.bytes_freed == 1234
        assert (prof / "Local Storage" / "leveldb").exists()


class TestElectron:
    def test_telegram_excluded_from_generic(self, fx):
        home, cache, cfg, ctx = fx
        for app in ("telegram-desktop", "some-electron-app"):
            (cfg / app / "Cache").mkdir(parents=True)
            (cfg / app / "Cache" / "f").write_bytes(b"x")
        p = ElectronAppsProvider(ctx)
        paths = [cp.path for cp in p.cache_paths()]
        assert len(paths) == 1
        assert "some-electron-app" in paths[0]

    def test_vscode_workspace_storage_is_conditional(self, fx):
        home, cache, cfg, ctx = fx
        (cfg / "Code" / "Cache").mkdir(parents=True)
        (cfg / "Code" / "User" / "workspaceStorage").mkdir(parents=True)
        p = VSCodeProvider(ctx)
        levels = {os.path.basename(cp.path): cp.safety for cp in p.cache_paths()}
        assert levels["Cache"] is SafetyLevel.SAFE_CACHE
        assert levels["workspaceStorage"] is SafetyLevel.CONDITIONAL_CACHE

    def test_conditional_not_cleaned_without_approval(self, fx):
        home, cache, cfg, ctx = fx
        ws = cfg / "Code" / "User" / "workspaceStorage"
        ws.mkdir(parents=True)
        (ws / "state.vscdb").write_bytes(b"s" * 777)
        p = VSCodeProvider(ctx)
        r = p.clean(include_conditional=False)
        assert (ws / "state.vscdb").exists()
        assert r.skipped_paths == 1
        r2 = p.clean(include_conditional=True)
        assert r2.bytes_freed == 777


class TestDetectionOnFixture:
    def test_layered_detection(self, fx):
        home, cache, cfg, ctx = fx
        os.makedirs(home / ".cache" / "pip")
        os.makedirs(home / ".cache" / "yay" / "somepkg")
        os.makedirs(cfg / "brave-browser" / "Default" / "Cache")
        det = {p.id for p in detect_all(ctx)}
        assert {"lang.pip", "pkgman.yay", "browser.brave"} <= det

    def test_no_cache_detected(self, fx):
        _, _, _, ctx = fx
        assert detect_all(ctx) == []


# ================================================================ E-011: pacman
from unittest import mock

from cachecleaner.core import elevation
from cachecleaner.core.elevation import ElevationResult, ElevationStatus
from cachecleaner.providers.pkgman import PacmanCacheProvider


def _pacman_fixture(tmp_path):
    target = tmp_path / "pkg"
    target.mkdir()
    for name, n in (("a-1-1-x86_64.pkg.tar.zst", 4000),
                    ("b-2-1-x86_64.pkg.tar.zst", 6000)):
        (target / name).write_bytes(b"x" * n)
    return target


def _provider(ctx, target):
    p = PacmanCacheProvider(ctx)
    p._target = str(target)
    return p


class TestPacmanElevation:
    def test_detect_and_size(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)
        assert p.detect()
        assert p.calculate_size().bytes == 10_000
        assert p.needs_elevation() is False     # user-owned tmp dir

    def test_clean_success_via_helper_is_verified(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)

        def fake_run(keep=0, **kw):            # helper deletes everything
            for f in target.iterdir():
                f.unlink()
            return ElevationResult(ElevationStatus.SUCCESS, 10_000, 0)

        with mock.patch.object(p, "needs_elevation", return_value=True), \
             mock.patch.object(elevation, "run_paccache", side_effect=fake_run):
            r = p.clean(include_conditional=True)
        assert r.bytes_freed == 10_000          # measured before/after
        assert len(r.errors) == 0

    def test_cancelled_message_and_no_change(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)
        with mock.patch.object(p, "needs_elevation", return_value=True), \
             mock.patch.object(elevation, "run_paccache",
                               return_value=ElevationResult(ElevationStatus.CANCELLED)):
            r = p.clean()
        assert r.errors.records[0].detail == "Pacman cache cleanup cancelled."
        assert sum(f.stat().st_size for f in target.iterdir()) == 10_000

    def test_auth_failed_message_and_no_change(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)
        with mock.patch.object(p, "needs_elevation", return_value=True), \
             mock.patch.object(elevation, "run_paccache",
                               return_value=ElevationResult(ElevationStatus.AUTH_FAILED)):
            r = p.clean()
        assert r.errors.records[0].detail == (
            "Authentication failed. Pacman cache was not modified.")
        assert len(list(target.iterdir())) == 2

    def test_partial_cleanup_never_reports_success(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)

        def partial(keep=0, **kw):             # helper could only remove one
            (target / "a-1-1-x86_64.pkg.tar.zst").unlink()
            return ElevationResult(ElevationStatus.SUCCESS, 4000, 6000)

        with mock.patch.object(p, "needs_elevation", return_value=True), \
             mock.patch.object(elevation, "run_paccache", side_effect=partial):
            r = p.clean()
        assert r.bytes_freed == 4_000
        assert len(r.errors) == 1
        assert "completed with errors" in r.errors.records[0].detail
        assert "remaining: 6000" in r.errors.records[0].detail

    def test_dry_run_plans_without_deleting(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)
        with mock.patch.object(p, "needs_elevation", return_value=True):
            r = p.clean(dry_run=True)
        assert r.bytes_freed == 10_000
        assert len(list(target.iterdir())) == 2

    def test_helper_missing_classified(self, fx):
        home, cache, cfg, ctx = fx
        target = _pacman_fixture(home)
        p = _provider(ctx, target)
        with mock.patch.object(p, "needs_elevation", return_value=True), \
             mock.patch.object(elevation, "run_paccache",
                               return_value=ElevationResult(
                                   ElevationStatus.HELPER_MISSING)):
            r = p.clean()
        assert "not" in r.errors.records[0].detail.lower()  # 'not installed'
