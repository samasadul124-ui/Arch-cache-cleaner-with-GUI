"""Package-manager cache providers (pacman, yay, paru, flatpak).

pacman's cache is root-owned. It is a first-class provider (bug report §5):
detected, measured, and — when cleaning requires root — the app triggers the
system polkit authentication dialog itself and delegates deletion to the
isolated audited helper (rule 7, E-011). The app never sees a password and
the GUI never runs as root.
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional

from ..core import elevation
from ..core.errors import ErrorBucket, ErrorKind
from ..core.fs import dir_size
from ..core.provider import (CachePath, CacheProvider, Category,
                             ProviderCleanResult)
from ..core.safety import SafetyLevel

__all__ = ["PacmanCacheProvider", "YayProvider", "ParuProvider", "FlatpakProvider"]

PACMAN_PKG_CACHE = "/var/cache/pacman/pkg"


class PacmanCacheProvider(CacheProvider):
    id = "pkgman.pacman"
    name = "pacman package cache"
    category = Category.PACKAGE_MANAGER
    safety = SafetyLevel.CONDITIONAL_CACHE
    #: versions kept per package when cleaning via the helper (0 = full clean,
    #: matching the size shown in the UI)
    keep_versions = 0

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._target = PACMAN_PKG_CACHE      # tests may redirect

    def detect(self) -> bool:
        return os.path.isdir(self._target)

    def cache_paths(self) -> list[CachePath]:
        return [CachePath(
            self._target,
            "Downloaded package files kept by pacman (rollback source)",
            SafetyLevel.CONDITIONAL_CACHE,
        )]

    def needs_elevation(self) -> bool:
        return not os.access(self._target, os.W_OK)

    def explain(self) -> str:
        return ("Deletes the downloaded .pkg.tar.zst files pacman keeps in "
                "/var/cache/pacman/pkg. The system authentication dialog will "
                "appear because this folder belongs to the administrator. "
                "Packages are re-downloaded from the mirrors if needed, but "
                "downgrading without network becomes impossible. To keep the "
                "2 newest versions per package instead, run: "
                "pkexec cachecleaner-paccache 2")

    # ------------------------------------------------------- cleaning (E-011)
    def clean(
        self,
        dry_run: bool = False,
        cancel: Optional[threading.Event] = None,
        progress: Optional[Callable[[int, int], None]] = None,
        include_conditional: bool = False,
    ) -> ProviderCleanResult:
        res = ProviderCleanResult(provider_id=self.id, attempted=True)
        if not os.path.isdir(self._target):
            return res

        before = dir_size(self._target).bytes

        if dry_run:
            res.cleaned_paths = 1
            res.bytes_freed = before          # planned amount
            return res

        if not self.needs_elevation():
            # rare: cache dir is user-writable → normal validated clean
            return super().clean(dry_run=dry_run, cancel=cancel,
                                 progress=progress,
                                 include_conditional=True)

        if cancel is not None and cancel.is_set():
            res.cancelled = True
            return res

        er = elevation.run_paccache(keep=self.keep_versions)

        if er.status is elevation.ElevationStatus.SUCCESS:
            # ---- verification (report §8): fresh measurement, no assumptions
            after = dir_size(self._target).bytes
            freed = max(0, before - after)
            res.cleaned_paths = 1
            res.bytes_freed = freed
            if after > 0 and self.keep_versions == 0:
                # files remain despite a full-clean request → partial failure,
                # never report success (report §5)
                res.errors.add(
                    ErrorKind.PROVIDER_FAILURE, self._target, self.id,
                    f"Cleanup completed with errors. Removed: {freed} B, "
                    f"remaining: {after} B")
        elif er.status is elevation.ElevationStatus.CANCELLED:
            res.errors.add(ErrorKind.CANCELLED, self._target, self.id,
                           "Pacman cache cleanup cancelled.")
        elif er.status is elevation.ElevationStatus.AUTH_FAILED:
            res.errors.add(ErrorKind.INSUFFICIENT_PRIVILEGES, self._target,
                           self.id, "Authentication failed. Pacman cache was "
                                    "not modified.")
        else:  # helper_error / helper_missing / launch_error
            res.errors.add(ErrorKind.INSUFFICIENT_PRIVILEGES, self._target,
                           self.id, er.user_message()
                           + (f" ({er.detail})" if er.detail else ""))
        return res


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
