"""Provider registry.

Adding a new cache source:
  1. create a CacheProvider subclass in one of the modules (or a new module),
  2. append it to PROVIDER_CLASSES below.
No UI or engine changes needed (rule 3).
"""

from __future__ import annotations

from typing import Sequence

from ..core.provider import CacheProvider, ProviderContext
from .browsers import (BraveProvider, ChromeProvider, ChromiumProvider,
                       EdgeProvider, FirefoxProvider, OperaProvider,
                       VivaldiProvider)
from .electron import ElectronAppsProvider, VSCodiumProvider, VSCodeProvider
from .langtools import (CargoProvider, CcacheProvider, GoBuildCacheProvider,
                        GradleProvider, MavenProvider, NpmProvider,
                        PipProvider, PnpmProvider, RustupProvider,
                        YarnProvider)
from .pkgman import (DebtapProvider, FlatpakProvider,
                     PacmanCacheProvider, ParuProvider, YayProvider)
from .sweep import CacheNameSweepProvider
from .xdg import (FontconfigProvider, KdeSycocaProvider,
                  MesaShaderCacheProvider, ThumbnailsProvider)

__all__ = ["PROVIDER_CLASSES", "instantiate_all", "detect_all",
         "CacheNameSweepProvider"]

PROVIDER_CLASSES: Sequence[type[CacheProvider]] = (
    # desktop / XDG
    ThumbnailsProvider, FontconfigProvider, MesaShaderCacheProvider,
    KdeSycocaProvider,
    # browsers
    FirefoxProvider, ChromeProvider, ChromiumProvider, BraveProvider,
    EdgeProvider, VivaldiProvider, OperaProvider,
    # package managers
    PacmanCacheProvider, DebtapProvider, YayProvider, ParuProvider,
    FlatpakProvider,
    # language toolchains
    NpmProvider, PnpmProvider, YarnProvider, PipProvider,
    GoBuildCacheProvider, CargoProvider, RustupProvider, CcacheProvider,
    GradleProvider, MavenProvider,
    # applications
    VSCodeProvider, VSCodiumProvider, ElectronAppsProvider,
)


def instantiate_all(ctx: ProviderContext) -> list[CacheProvider]:
    return [cls(ctx) for cls in PROVIDER_CLASSES]


def detect_all(ctx: ProviderContext) -> list[CacheProvider]:
    """Instantiate every provider and keep the ones that detected their cache."""
    detected: list[CacheProvider] = []
    for provider in instantiate_all(ctx):
        try:
            if provider.detect():
                provider.detected = True
                detected.append(provider)
        except OSError:
            continue
    return detected
