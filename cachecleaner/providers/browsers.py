"""Browser cache providers.

SAFETY: only well-known cache *subdirectories* of browser profiles are ever
listed. The profile directory itself, bookmarks, history, cookies, logins,
keyrings and extension data are structurally unreachable from here.
"""

from __future__ import annotations

import os
from typing import ClassVar

from ..core.provider import CachePath, CacheProvider, Category
from ..core.safety import SafetyLevel

__all__ = ["FirefoxProvider"] + [
    f"{n}Provider" for n in
    ("Chrome", "Chromium", "Brave", "Edge", "Vivaldi", "Opera")
]

# Chromium profile subdirectories that hold purely regenerable cache data.
_CHROMIUM_CACHE_SUBDIRS = (
    ("Cache", "HTTP disk cache"),
    ("Code Cache", "Compiled JS/WASM code cache"),
    ("GPUCache", "GPU shader cache"),
    ("DawnGraphiteCache", "Dawn/Graphite GPU cache"),
    ("DawnWebGPSCache", "WebGPU shader cache"),
    ("Service Worker/CacheStorage", "Service-worker offline cache"),
    ("Service Worker/ScriptCache", "Service-worker script cache"),
)


class FirefoxProvider(CacheProvider):
    id = "browser.firefox"
    name = "Firefox"
    category = Category.BROWSER
    safety = SafetyLevel.SAFE_CACHE

    def _profile_roots(self) -> list[str]:
        home = self.ctx.home
        candidates = [
            os.path.join(home, ".mozilla", "firefox"),
            os.path.join(self.ctx.xdg_cache, "mozilla", "firefox"),
            os.path.join(home, ".var", "app", "org.mozilla.firefox", ".mozilla", "firefox"),
        ]
        return [c for c in candidates if os.path.isdir(c)]

    def detect(self) -> bool:
        return bool(self._profile_roots())

    def cache_paths(self) -> list[CachePath]:
        paths: list[CachePath] = []
        for root in self._profile_roots():
            try:
                entries = os.listdir(root)
            except OSError:
                continue
            for e in entries:
                c2 = os.path.join(root, e, "cache2")
                if os.path.isdir(c2):
                    paths.append(CachePath(
                        c2, f"Firefox profile '{e}' disk cache",
                        SafetyLevel.SAFE_CACHE))
        return paths

    def explain(self) -> str:
        return ("Deletes only the 'cache2' disk-cache folder of each Firefox "
                "profile. Bookmarks, history, passwords, cookies, sessions and "
                "add-ons are NOT touched. Sites may load slightly slower once.")


class _ChromiumProvider(CacheProvider):
    """Shared logic for Chromium-derivative browsers."""

    config_dir: ClassVar[str] = ""
    product: ClassVar[str] = ""
    category = Category.BROWSER
    safety = SafetyLevel.SAFE_CACHE

    def _root(self) -> str:
        return os.path.join(self.ctx.xdg_config, self.config_dir)

    def detect(self) -> bool:
        return os.path.isdir(self._root())

    def cache_paths(self) -> list[CachePath]:
        root = self._root()
        paths: list[CachePath] = []
        try:
            profiles = [os.path.join(root, d) for d in os.listdir(root)
                        if os.path.isdir(os.path.join(root, d))]
        except OSError:
            return paths
        for prof in profiles:
            for sub, purpose in _CHROMIUM_CACHE_SUBDIRS:
                p = os.path.join(prof, sub)
                if os.path.isdir(p):
                    paths.append(CachePath(
                        p, f"{self.product} ({os.path.basename(prof)}): {purpose}",
                        SafetyLevel.SAFE_CACHE))
        return paths

    def explain(self) -> str:
        return (f"Deletes only regenerable cache folders inside {self.product} "
                "profiles (disk cache, code cache, GPU cache, service-worker "
                "cache). Passwords, bookmarks, history, cookies, sessions and "
                "extensions are NOT touched.")


class ChromeProvider(_ChromiumProvider):
    id, config_dir, product = "browser.chrome", "google-chrome", "Google Chrome"
    name = "Google Chrome"


class ChromiumProvider(_ChromiumProvider):
    id, config_dir, product = "browser.chromium", "chromium", "Chromium"
    name = "Chromium"


class BraveProvider(_ChromiumProvider):
    id, config_dir, product = "browser.brave", "brave-browser", "Brave"
    name = "Brave"


class EdgeProvider(_ChromiumProvider):
    id, config_dir, product = "browser.edge", "microsoft-edge", "Microsoft Edge"
    name = "Microsoft Edge"


class VivaldiProvider(_ChromiumProvider):
    id, config_dir, product = "browser.vivaldi", "vivaldi", "Vivaldi"
    name = "Vivaldi"


class OperaProvider(_ChromiumProvider):
    id, config_dir, product = "browser.opera", "opera", "Opera"
    name = "Opera"
