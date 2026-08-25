"""CacheProvider interface and shared provider infrastructure (rule 3).

A provider declares *what* is cache, *where* it lives and *how safe* deletion
is. The defaults below implement size measurement, cleaning and verification
on top of ``fs.py`` + ``safety.py``, so a new provider only has to declare
paths and safety levels — no UI or engine changes required.
"""

from __future__ import annotations

import os
import shutil
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, ClassVar, Optional

from .errors import ErrorBucket, ErrorKind
from .fs import DeleteResult, SizeResult, delete_contents, dir_size
from .safety import PathSafety, SafetyLevel

__all__ = [
    "Category", "CachePath", "ProviderContext", "ProviderCleanResult",
    "CacheProvider",
]


class Category(Enum):
    BROWSER = "Browser"
    PACKAGE_MANAGER = "Package manager"
    LANGUAGE_TOOL = "Language / toolchain"
    BUILD_TOOL = "Build system"
    APPLICATION = "Application"
    DESKTOP = "Desktop environment"
    SYSTEM = "System"


@dataclass(frozen=True)
class CachePath:
    """One concrete cache location belonging to a provider."""

    path: str
    purpose: str                       # shown in the UI, e.g. "Disk cache"
    safety: SafetyLevel = SafetyLevel.SAFE_CACHE
    exists: Optional[bool] = None      # filled by provider/scan


@dataclass
class ProviderContext:
    """Environment handed to every provider (home dirs, safety validator)."""

    home: str
    xdg_cache: str
    xdg_config: str
    xdg_data: str
    safety: PathSafety

    def which(self, binary: str) -> bool:
        return shutil.which(binary) is not None

    def expand(self, p: str) -> str:
        return os.path.normpath(os.path.expandvars(os.path.expanduser(p)))


@dataclass
class ProviderCleanResult:
    provider_id: str
    attempted: bool = False
    cleaned_paths: int = 0
    skipped_paths: int = 0
    bytes_freed: int = 0
    files_deleted: int = 0
    cancelled: bool = False
    refused: bool = False
    errors: ErrorBucket = field(default_factory=ErrorBucket)

    @property
    def ok(self) -> bool:
        return self.attempted and not self.refused and len(self.errors) == 0


class CacheProvider(ABC):
    """Base class for every cache source."""

    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    category: ClassVar[Category] = Category.APPLICATION
    safety: ClassVar[SafetyLevel] = SafetyLevel.SAFE_CACHE

    def __init__(self, ctx: ProviderContext) -> None:
        self.ctx = ctx
        self._size_cache: Optional[SizeResult] = None
        self.last_size: int = 0
        self.detected: bool = False

    # ------------------------------------------------------------ interface
    @abstractmethod
    def detect(self) -> bool:
        """Return True when this software/cache is present on the system."""

    @abstractmethod
    def cache_paths(self) -> list[CachePath]:
        """Concrete cache locations (call after detect() == True)."""

    def explain(self) -> str:
        """UI explanation of what cleaning removes and what the impact is."""
        return (f"Removes cached data of {self.name}. "
                "The application recreates these files automatically when needed.")

    # ------------------------------------------------------- default engine
    def active_paths(self) -> list[CachePath]:
        """Existing paths, annotated with exists flag."""
        out: list[CachePath] = []
        for cp in self.cache_paths():
            exists = os.path.exists(cp.path)
            out.append(CachePath(cp.path, cp.purpose, cp.safety, exists))
        return out

    def calculate_size(self, include_protected: bool = True) -> SizeResult:
        """Measured bytes across existing paths. Cached until next scan."""
        res = SizeResult()
        for cp in self.active_paths():
            if not cp.exists:
                continue
            if cp.safety is SafetyLevel.DO_NOT_DELETE and not include_protected:
                continue
            part = dir_size(cp.path, errors=res.errors)
            res.bytes += part.bytes
            res.files += part.files
            res.dirs += part.dirs
            res.symlinks += part.symlinks
        self._size_cache = res
        self.last_size = res.bytes
        return res

    def clean(
        self,
        dry_run: bool = False,
        cancel: Optional[threading.Event] = None,
        progress: Optional[Callable[[int, int], None]] = None,
        include_conditional: bool = False,
    ) -> ProviderCleanResult:
        """Clean all eligible paths; per-path errors never abort the run."""
        res = ProviderCleanResult(provider_id=self.id)
        res.attempted = True
        for cp in self.active_paths():
            if cancel is not None and cancel.is_set():
                res.cancelled = True
                break
            if not cp.exists:
                continue
            eligible = cp.safety is SafetyLevel.SAFE_CACHE or (
                cp.safety is SafetyLevel.CONDITIONAL_CACHE and include_conditional
            )
            if not eligible:
                res.skipped_paths += 1
                continue
            dr: DeleteResult = delete_contents(
                cp.path, self.ctx.safety, dry_run=dry_run, cancel=cancel,
                progress=progress,
            )
            if dr.refused:
                res.skipped_paths += 1
                res.errors.add(ErrorKind.INVALID_PATH, cp.path, self.id, dr.refuse_reason)
                continue
            res.cleaned_paths += 1
            res.bytes_freed += dr.bytes_freed
            res.files_deleted += dr.files_deleted
            res.cancelled = res.cancelled or dr.cancelled
            for rec in dr.errors.records:
                rec.provider = self.id
                res.errors.records.append(rec)
            if dr.cancelled:
                break
        return res

    def verify(self) -> tuple[int, bool]:
        """Post-cleanup re-measurement. Returns (remaining_bytes, ok)."""
        self._size_cache = None
        remaining = self.calculate_size(include_protected=True).bytes
        # A provider is 'ok' when nothing eligible remains beyond protected data.
        eligible_left = 0
        for cp in self.active_paths():
            if cp.exists and cp.safety is not SafetyLevel.DO_NOT_DELETE:
                eligible_left += dir_size(cp.path).bytes
        return remaining, eligible_left == 0
