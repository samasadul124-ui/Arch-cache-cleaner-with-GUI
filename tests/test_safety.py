"""Safety/path-validation test matrix (rule 16).

All fixtures live inside tmp_path — the real $HOME is never referenced.
"""

from __future__ import annotations

import os

import pytest

from cachecleaner.core.safety import (
    NAME_DENYLIST,
    PathSafety,
    SafetyLevel,
    default_user_roots,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated fake home with ~/.cache as the only allowed root."""
    home = tmp_path / "home" / "user"
    cache = home / ".cache"
    cache.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    safety = PathSafety(home=str(home), allowed_roots=[str(cache)])
    return home, cache, safety


class TestHardRejections:
    def test_root_rejected(self, env):
        _, _, s = env
        assert not s.validate("/")

    def test_home_dir_rejected(self, env):
        _, _, s = env
        assert not s.validate("/home")

    def test_user_home_rejected(self, env):
        home, _, s = env
        assert not s.validate(str(home))

    def test_empty_rejected(self, env):
        _, _, s = env
        assert not s.validate("")
        assert not s.validate("   ")

    def test_relative_rejected(self, env):
        _, _, s = env
        assert not s.validate(".cache/foo")

    def test_dotdot_traversal_rejected(self, env):
        _, cache, s = env
        assert not s.validate(str(cache / "a" / ".." / ".." / "etc"))

    @pytest.mark.parametrize(
        "path",
        ["/etc/passwd", "/usr/share", "/boot/vmlinuz", "/var/lib/pacman/local",
         "/bin/sh", "/root", "/proc/1", "/sys/kernel"],
    )
    def test_system_paths_rejected(self, env, path):
        _, _, s = env
        assert not s.validate(path), path

    def test_shallow_path_rejected(self, env):
        # an allowed-but-shallow path (2 components) is still refused
        p = PathSafety(home="/home/nobody", allowed_roots=["/opt/cache-root"])
        res = p.validate("/opt/cache-root")
        assert not res.ok
        assert "shallow" in res.reason


class TestDenylist:
    def test_tdata_inside_cache_rejected(self, env):
        _, cache, s = env
        assert not s.validate(str(cache / "telegram" / "tdata"))

    def test_gnupg_rejected(self, env):
        _, cache, s = env
        assert not s.validate(str(cache / "app" / ".gnupg"))

    def test_browser_profile_data_rejected(self, env):
        _, cache, s = env
        for name in ("IndexedDB", "Local Storage", "databases", "cookies.sqlite"):
            assert not s.validate(str(cache / "browser" / name)), name

    def test_denylist_is_not_empty(self):
        assert len(NAME_DENYLIST) > 20


class TestValidPaths:
    def test_plain_cache_dir_ok(self, env):
        _, cache, s = env
        (cache / "myapp").mkdir()
        assert s.validate(str(cache / "myapp"))

    def test_nested_cache_file_ok(self, env):
        _, cache, s = env
        assert s.validate(str(cache / "myapp" / "shader.cache"))

    def test_cache_root_itself_ok(self, env):
        _, cache, s = env
        assert s.validate(str(cache))


class TestSymlinkDefence:
    def test_symlink_escaping_root_rejected(self, env):
        _, cache, s = env
        evil = cache / "evil-link"
        os.symlink("/etc", evil)
        res = s.validate(str(evil))
        assert not res.ok
        assert "resolves outside" in res.reason or "denied" in res.reason

    def test_symlink_file_escaping_root_rejected(self, env):
        home, cache, s = env
        secret = home / "secret.txt"
        secret.write_text("do not delete")
        link = cache / "app"
        link.mkdir()
        sneaky = link / "data"
        os.symlink(secret, sneaky)
        assert not s.validate(str(sneaky))

    def test_symlinked_cache_root_itself_still_works(self, env, tmp_path):
        home, _, _ = env
        real_store = tmp_path / "elsewhere" / "cache-store"
        real_store.mkdir(parents=True)
        link_cache = home / ".cache-link"
        os.symlink(real_store, link_cache)
        s = PathSafety(home=str(home), allowed_roots=[str(link_cache)])
        assert s.validate(str(link_cache / "app" / "files"))


class TestSystemRoots:
    def test_pacman_cache_allowed_when_explicit(self, tmp_path):
        root = "/var/cache/pacman/pkg"
        s = PathSafety(home="/home/nobody", allowed_roots=[root])
        assert s.validate(root + "/firefox-120-1-x86_64.pkg.tar.zst").ok

    def test_var_rejected_without_allowlist(self, tmp_path):
        s = PathSafety(home="/home/nobody", allowed_roots=["/home/nobody/.cache"])
        assert not s.validate("/var/cache/pacman/pkg/x")


class TestMisc:
    def test_default_user_roots_include_xdg(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        roots = default_user_roots(str(tmp_path))
        assert str(tmp_path / ".cache") in roots
        assert str(tmp_path / ".npm") in roots

    def test_validator_never_raises(self, env):
        _, _, s = env
        for weird in (None, 123, b"/etc", ["x"]):  # type: ignore[arg-type]
            res = s.validate(weird)  # type: ignore[arg-type]
            assert not res.ok

    def test_safety_level_enum(self):
        assert SafetyLevel.SAFE_CACHE.value == "safe"
        assert SafetyLevel.CONDITIONAL_CACHE.value == "conditional"
        assert SafetyLevel.DO_NOT_DELETE.value == "protected"
