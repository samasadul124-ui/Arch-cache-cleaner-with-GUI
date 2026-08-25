"""Electron-app cache providers: VS Code, VSCodium, plus a dynamic provider
that discovers cache dirs of *other* installed Electron apps under ~/.config.

SAFETY: Telegram Desktop is explicitly excluded — its config dir contains
session data (tdata) that must never be deleted (rule 5.2). Browsers handled
by providers/browsers.py are skipped to avoid double counting.
"""

from __future__ import annotations

import os
from typing import ClassVar

from ..core.provider import CachePath, CacheProvider, Category
from ..core.safety import SafetyLevel

__all__ = ["VSCodeProvider", "VSCodiumProvider", "ElectronAppsProvider"]

# Electron cache subdirs that hold purely regenerable data.
_ELECTRON_CACHE_SUBDIRS = ("Cache", "Code Cache", "GPUCache", "CachedData")

# Config dirs that must never be swept by the generic provider.
_GENERIC_EXCLUDES = frozenset({
    "telegram-desktop", "telegramdesktop", "Telegram Desktop",
    # browser providers own these:
    "google-chrome", "chromium", "brave-browser", "microsoft-edge",
    "vivaldi", "opera",
    # dedicated providers own these:
    "Code", "VSCodium",
})


class _VscodeLikeProvider(CacheProvider):
    config_dir: ClassVar[str] = ""
    product: ClassVar[str] = ""

    category = Category.APPLICATION
    safety = SafetyLevel.SAFE_CACHE

    def _root(self) -> str:
        return os.path.join(self.ctx.xdg_config, self.config_dir)

    def detect(self) -> bool:
        return os.path.isdir(self._root())

    def cache_paths(self) -> list[CachePath]:
        root = self._root()
        paths = []
        for sub in _ELECTRON_CACHE_SUBDIRS:
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                paths.append(CachePath(p, f"{self.product}: {sub}",
                                       SafetyLevel.SAFE_CACHE))
        # per-profile caches (Code - User - workspaceStorage caches)
        for prof in ("User",):
            for sub in ("workspaceStorage",):
                p = os.path.join(root, prof, sub)
                if os.path.isdir(p):
                    paths.append(CachePath(
                        p, f"{self.product}: per-workspace cache storage",
                        SafetyLevel.CONDITIONAL_CACHE))
        return paths

    def explain(self) -> str:
        return (f"Removes regenerable cache folders of {self.product} "
                "(disk/code/GPU cache). Extensions, settings, keybindings and "
                "workspace state are NOT touched.")


class VSCodeProvider(_VscodeLikeProvider):
    id, name, config_dir, product = "app.vscode", "VS Code", "Code", "VS Code"


class VSCodiumProvider(_VscodeLikeProvider):
    id, name, config_dir, product = "app.vscodium", "VSCodium", "VSCodium", "VSCodium"


class ElectronAppsProvider(CacheProvider):
    """Discovers cache dirs of Electron apps not covered by dedicated providers."""

    id = "app.electron-other"
    name = "Other Electron apps"
    category = Category.APPLICATION
    safety = SafetyLevel.SAFE_CACHE

    def _scan(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        cfg = self.ctx.xdg_config
        try:
            apps = sorted(os.listdir(cfg))
        except OSError:
            return found
        for app in apps:
            if app in _GENERIC_EXCLUDES or app.startswith("."):
                continue
            app_dir = os.path.join(cfg, app)
            if not os.path.isdir(app_dir):
                continue
            for sub in _ELECTRON_CACHE_SUBDIRS:
                p = os.path.join(app_dir, sub)
                if os.path.isdir(p):
                    found.append((app, p))
        return found

    def detect(self) -> bool:
        return bool(self._scan())

    def cache_paths(self) -> list[CachePath]:
        return [CachePath(p, f"{app}: {os.path.basename(p)}", SafetyLevel.SAFE_CACHE)
                for app, p in self._scan()]

    def explain(self) -> str:
        return ("Removes Chromium-style disk/GPU caches of Electron apps "
                "installed on this system (except Telegram, which stores "
                "session data in its config dir, and browsers covered "
                "separately). App settings and accounts stay intact.")
