"""Layered system/software discovery (rule 13).

Layers implemented:
  3 — installed software: pacman package list (when available), PATH binaries;
  4 — user-directory targeted: unclaimed children of ``~/.cache`` become the
      dynamic "Other application caches" provider (XDG cache-home contract:
      everything there is regenerable cache data).

No full-disk scans, ever. Unknown children are still filtered through the
safety denylist before being offered for cleaning.
"""

from __future__ import annotations

import os
import subprocess
from typing import Iterable, Optional

from .provider import CachePath, CacheProvider, Category, ProviderContext
from .safety import NAME_DENYLIST, SafetyLevel

__all__ = [
    "installed_packages", "binary_present", "claimed_cache_basenames",
    "OtherXdgCachesProvider",
]

_pacman_cache: Optional[frozenset[str]] = None


def installed_packages(ctx: ProviderContext) -> frozenset[str]:
    """Query pacman for the package list (cached). Empty set if unavailable."""
    global _pacman_cache
    if _pacman_cache is not None:
        return _pacman_cache
    pkgs: set[str] = set()
    if binary_present(ctx, "pacman"):
        try:
            out = subprocess.run(
                ["pacman", "-Qq"], capture_output=True, text=True, timeout=30)
            if out.returncode == 0:
                pkgs = {line.strip() for line in out.stdout.splitlines() if line.strip()}
        except (OSError, subprocess.SubprocessError):
            pkgs = set()
    _pacman_cache = frozenset(pkgs)
    return _pacman_cache


def binary_present(ctx: ProviderContext, name: str) -> bool:
    return ctx.which(name)


def claimed_cache_basenames(ctx: ProviderContext,
                            providers: Iterable[CacheProvider]) -> set[str]:
    """Top-level ~/.cache names already owned by dedicated providers."""
    claimed: set[str] = set()
    cache_root = os.path.normpath(ctx.xdg_cache)
    for p in providers:
        try:
            paths = p.cache_paths()
        except OSError:
            continue
        for cp in paths:
            np = os.path.normpath(cp.path)
            if np == cache_root or not np.startswith(cache_root + os.sep):
                continue
            rel = np[len(cache_root) + 1:]
            top = rel.split(os.sep)[0]
            if top:
                claimed.add(top)
    return claimed


class OtherXdgCachesProvider(CacheProvider):
    """Groups every unclaimed, non-denylisted child of ~/.cache."""

    id = "xdg.other"
    name = "Other application caches"
    category = Category.APPLICATION
    safety = SafetyLevel.SAFE_CACHE

    def __init__(self, ctx: ProviderContext, claimed: set[str]) -> None:
        super().__init__(ctx)
        self._claimed = claimed

    def _children(self) -> list[str]:
        out: list[str] = []
        try:
            entries = sorted(os.listdir(self.ctx.xdg_cache))
        except OSError:
            return out
        for name in entries:
            if name.startswith(".") or name in self._claimed or name in NAME_DENYLIST:
                continue
            p = os.path.join(self.ctx.xdg_cache, name)
            if os.path.isdir(p) and not os.path.islink(p):
                out.append(p)
        return out

    def detect(self) -> bool:
        return bool(self._children())

    def cache_paths(self) -> list[CachePath]:
        return [CachePath(p, f"{os.path.basename(p)} cache directory",
                          SafetyLevel.SAFE_CACHE) for p in self._children()]

    def explain(self) -> str:
        return ("Application cache folders in ~/.cache that have no dedicated "
                "provider. By the XDG standard this directory holds only "
                "regenerable cache data; applications recreate what they need. "
                "Hidden folders and denylisted names (sessions, keyrings, …) "
                "are excluded.")
