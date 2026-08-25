"""Package-manager cache providers (pacman, yay, paru, flatpak).

pacman's cache is system-owned: it is classified CONDITIONAL_CACHE and the
engine reports that elevation is required; actual deletion is delegated to a
separate minimal helper invoked via pkexec (rule 7) — this module only
measures and plans.
"""

from __future__ import annotations

import os

from ..core.provider import CachePath, CacheProvider, Category
from ..core.safety import SafetyLevel

__all__ = ["PacmanCacheProvider", "YayProvider", "ParuProvider", "FlatpakProvider"]

PACMAN_PKG_CACHE = "/var/cache/pacman/pkg"


class PacmanCacheProvider(CacheProvider):
    id = "pkgman.pacman"
    name = "pacman package cache"
    category = Category.PACKAGE_MANAGER
    safety = SafetyLevel.CONDITIONAL_CACHE

    def detect(self) -> bool:
        return os.path.isdir(PACMAN_PKG_CACHE)

    def cache_paths(self) -> list[CachePath]:
        return [CachePath(
            PACMAN_PKG_CACHE,
            "Downloaded package files kept by pacman (rollback source)",
            SafetyLevel.CONDITIONAL_CACHE,
        )]

    def needs_elevation(self) -> bool:
        return not os.access(PACMAN_PKG_CACHE, os.W_OK)

    def explain(self) -> str:
        return ("Deletes the downloaded .pkg.tar.zst files pacman keeps in "
                "/var/cache/pacman/pkg. Packages are re-downloaded from the "
                "mirrors if needed, but downgrading without network becomes "
                "impossible. Requires administrator privileges (separate "
                "helper, one-time authentication). Recommended alternative: "
                "'paccache -rk2' keeps the 2 newest versions.")


class _AurHelperProvider(CacheProvider):
    binary: str = ""
    cache_subdir: str = ""

    category = Category.PACKAGE_MANAGER
    safety = SafetyLevel.SAFE_CACHE

    def _root(self) -> str:
        return os.path.join(self.ctx.xdg_cache, self.cache_subdir)

    def detect(self) -> bool:
        return os.path.isdir(self._root())

    def cache_paths(self) -> list[CachePath]:
        if os.path.isdir(self._root()):
            return [CachePath(
                self._root(),
                f"{self.binary} AUR build cache (sources + built packages)",
                SafetyLevel.SAFE_CACHE,
            )]
        return []

    def explain(self) -> str:
        return (f"Deletes {self.binary}'s cache of AUR sources and built "
                "packages. AUR packages will be fetched and rebuilt from "
                "scratch next time they are updated. Installed packages and "
                "configuration are NOT touched.")


class YayProvider(_AurHelperProvider):
    id, name, binary, cache_subdir = "pkgman.yay", "yay", "yay", "yay"


class ParuProvider(_AurHelperProvider):
    id, name, binary, cache_subdir = "pkgman.paru", "paru", "paru", "paru"


class FlatpakProvider(CacheProvider):
    id = "pkgman.flatpak"
    name = "Flatpak"
    category = Category.PACKAGE_MANAGER
    safety = SafetyLevel.CONDITIONAL_CACHE

    def detect(self) -> bool:
        return os.path.isdir(os.path.join(self.ctx.xdg_cache, "flatpak"))

    def cache_paths(self) -> list[CachePath]:
        paths = []
        p = os.path.join(self.ctx.xdg_cache, "flatpak")
        if os.path.isdir(p):
            paths.append(CachePath(
                p, "Flatpak temporary download/system data",
                SafetyLevel.CONDITIONAL_CACHE))
        return paths

    def explain(self) -> str:
        return ("Removes Flatpak's temporary cache. Unused runtimes — usually "
                "the biggest share — are best removed with "
                "'flatpak uninstall --unused', which this tool can trigger for "
                "you after approval. Installed apps and their data stay intact.")
