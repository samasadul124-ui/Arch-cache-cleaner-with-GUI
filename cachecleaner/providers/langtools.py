"""Language / toolchain cache providers (npm, pnpm, yarn, pip, Go, Cargo,
rustup, ccache, Gradle, Maven).

Providers whose caches live OUTSIDE ``~/.cache`` declare ``extra_cache_roots``
so the engine can extend the path-safety allowlist explicitly — nothing is
ever whitelisted implicitly.
"""

from __future__ import annotations

import os
from typing import ClassVar

from ..core.provider import CachePath, CacheProvider, Category
from ..core.safety import SafetyLevel

__all__ = [
    "NpmProvider", "PnpmProvider", "YarnProvider", "PipProvider",
    "GoBuildCacheProvider", "CargoProvider", "RustupProvider",
    "CcacheProvider", "GradleProvider", "MavenProvider",
]


class _SimpleProvider(CacheProvider):
    """Declarative provider: one directory, one safety level."""

    binary: ClassVar[str] = ""
    relpath: ClassVar[str] = ""          # relative to $HOME
    purpose: ClassVar[str] = ""
    impact: ClassVar[str] = ""
    extra_cache_roots: ClassVar[tuple[str, ...]] = ()

    category = Category.LANGUAGE_TOOL

    def _path(self) -> str:
        return self.ctx.expand(os.path.join("~", self.relpath))

    def detect(self) -> bool:
        if os.path.isdir(self._path()):
            return True
        return bool(self.binary) and self.ctx.which(self.binary)

    def cache_paths(self) -> list[CachePath]:
        p = self._path()
        return [CachePath(p, self.purpose, self.safety)] if os.path.isdir(p) else []

    def explain(self) -> str:
        return f"Removes {self.name} cache data. {self.impact}"


class NpmProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.npm", "npm", "npm", ".npm/_cacache"
    safety = SafetyLevel.SAFE_CACHE
    purpose = "npm content-addressable package cache"
    impact = "Packages are re-downloaded on the next install (npm rebuilds the cache automatically)."


class PnpmProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.pnpm", "pnpm store", "pnpm", ".local/share/pnpm/store"
    safety = SafetyLevel.CONDITIONAL_CACHE
    purpose = "pnpm content-addressable store (shared across projects)"
    impact = ("Safe to remove, but pnpm will have to re-download every package "
              "for future installs — potentially several gigabytes of network traffic.")
    extra_cache_roots = ("~/.local/share/pnpm/store",)


class YarnProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.yarn", "Yarn (classic)", "yarn", ".cache/yarn"
    safety = SafetyLevel.SAFE_CACHE
    purpose = "Yarn v1 package cache"
    impact = "Packages are re-downloaded on the next install."


class PipProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.pip", "pip (Python)", "pip", ".cache/pip"
    safety = SafetyLevel.SAFE_CACHE
    purpose = "pip download/wheel cache"
    impact = "Equivalent to 'pip cache purge'; wheels are re-downloaded when needed."


class GoBuildCacheProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.go-build", "Go build cache", "go", ".cache/go-build"
    safety = SafetyLevel.SAFE_CACHE
    purpose = "Compiled Go package cache (GOCACHE)"
    impact = "Equivalent to 'go clean -cache'; the next Go build takes longer once."


class CargoProvider(CacheProvider):
    id = "lang.cargo"
    name = "Cargo (Rust)"
    category = Category.LANGUAGE_TOOL
    safety = SafetyLevel.SAFE_CACHE
    extra_cache_roots = ("~/.cargo/registry/cache",)

    def detect(self) -> bool:
        return os.path.isdir(os.path.join(self.ctx.home, ".cargo", "registry")) \
            or self.ctx.which("cargo")

    def cache_paths(self) -> list[CachePath]:
        reg = os.path.join(self.ctx.home, ".cargo", "registry")
        paths = []
        cache = os.path.join(reg, "cache")
        if os.path.isdir(cache):
            paths.append(CachePath(cache, "Downloaded crate archives (.crate files)",
                                   SafetyLevel.SAFE_CACHE))
        src = os.path.join(reg, "src")
        if os.path.isdir(src):
            paths.append(CachePath(src, "Extracted crate sources (re-extracted on demand)",
                                   SafetyLevel.CONDITIONAL_CACHE))
        return paths

    def explain(self) -> str:
        return ("Removes Cargo's downloaded crate archives (safe) and, with "
                "approval, extracted crate sources (regenerated on next build). "
                "Installed binaries in ~/.cargo/bin are NOT touched.")


class RustupProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.rustup", "rustup downloads", "rustup", ".rustup/downloads"
    safety = SafetyLevel.SAFE_CACHE
    purpose = "Toolchain installer downloads kept by rustup"
    impact = "Only installer artifacts; installed toolchains in ~/.rustup/toolchains stay intact."


class CcacheProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.ccache", "ccache", "ccache", ".cache/ccache"
    safety = SafetyLevel.CONDITIONAL_CACHE
    purpose = "Compiler output cache (C/C++)"
    impact = ("Safe to remove, but rebuilds lose their speed-up until the cache "
              "warms up again — noticeable on large C/C++ projects.")


class GradleProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.gradle", "Gradle", "gradle", ".gradle/caches"
    safety = SafetyLevel.CONDITIONAL_CACHE
    purpose = "Gradle dependency/build caches"
    impact = ("Safe to remove; the next Gradle build re-resolves dependencies "
              "(slow first build afterwards).")


class MavenProvider(_SimpleProvider):
    id, name, binary, relpath = "lang.maven", "Maven repository", "mvn", ".m2/repository"
    safety = SafetyLevel.CONDITIONAL_CACHE
    purpose = "Local Maven artifact repository"
    impact = ("Safe to remove, but every artifact is re-downloaded on the next "
              "build and offline builds stop working until then.")
