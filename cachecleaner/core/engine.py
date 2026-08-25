"""Cleaning engine: scan orchestration, plan/execute, fresh rescan (rules 5, 6, 14).

The engine is synchronous and thread-safe (cancel via ``threading.Event``);
the GUI/CLI run it inside their own worker threads so their event loops stay
responsive. Remaining size after a clean is ALWAYS a fresh measurement of the
filesystem — never ``before - removed`` arithmetic (rule 6).
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from . import log
from .discovery import OtherXdgCachesProvider, claimed_cache_basenames
from .errors import ErrorBucket, ErrorKind
from .provider import CacheProvider, ProviderCleanResult, ProviderContext
from .safety import PathSafety, SafetyLevel, default_user_roots
from ..providers import detect_all

__all__ = ["ProviderScan", "ScanReport", "CleanReport", "Engine"]

_logger = log.get_logger("engine")

ProgressCb = Callable[[float, str], None]      # (fraction 0..1, message)


@dataclass
class ProviderScan:
    provider: CacheProvider
    size_bytes: int = 0
    file_count: int = 0
    path_count: int = 0
    needs_elevation: bool = False


@dataclass
class ScanReport:
    scans: list[ProviderScan] = field(default_factory=list)
    total_bytes: int = 0
    duration: float = 0.0
    errors: ErrorBucket = field(default_factory=ErrorBucket)

    @property
    def provider_count(self) -> int:
        return len(self.scans)

    def by_id(self, provider_id: str) -> Optional[ProviderScan]:
        for s in self.scans:
            if s.provider.id == provider_id:
                return s
        return None


@dataclass
class CleanReport:
    dry_run: bool = False
    cancelled: bool = False
    before_bytes: int = 0
    after_bytes: Optional[int] = None       # fresh scan; None until rescan done
    per_provider: list[ProviderCleanResult] = field(default_factory=list)
    errors: ErrorBucket = field(default_factory=ErrorBucket)
    duration: float = 0.0

    # counts ---------------------------------------------------------------
    @property
    def cleaned(self) -> list[ProviderCleanResult]:
        return [r for r in self.per_provider if r.cleaned_paths > 0]

    @property
    def failed(self) -> list[ProviderCleanResult]:
        return [r for r in self.per_provider if len(r.errors) > 0]

    @property
    def skipped(self) -> list[ProviderCleanResult]:
        return [r for r in self.per_provider
                if r.cleaned_paths == 0 and len(r.errors) == 0]

    @property
    def removed_bytes(self) -> int:
        """Removed = two real measurements (rule 6), never arithmetic on one.

        For dry-runs nothing was deleted, so the number is the *planned*
        amount (sum of per-provider traversal counts).
        """
        if self.dry_run or self.after_bytes is None:
            return sum(r.bytes_freed for r in self.per_provider)
        return max(0, self.before_bytes - self.after_bytes)

    @property
    def ok(self) -> bool:
        return not self.failed and not self.cancelled


class Engine:
    """Builds contexts, runs scans and cleans."""

    def __init__(self, home: Optional[str] = None) -> None:
        self.home = os.path.normpath(home or os.path.expanduser("~"))
        self.ctx = self._build_context()

    # ------------------------------------------------------------ context
    def _build_context(self) -> ProviderContext:
        env = os.environ
        xdg_cache = env.get("XDG_CACHE_HOME") or os.path.join(self.home, ".cache")
        xdg_config = env.get("XDG_CONFIG_HOME") or os.path.join(self.home, ".config")
        xdg_data = env.get("XDG_DATA_HOME") or os.path.join(self.home, ".local", "share")
        safety = PathSafety(home=self.home, allowed_roots=default_user_roots(self.home))
        return ProviderContext(home=self.home, xdg_cache=xdg_cache,
                               xdg_config=xdg_config, xdg_data=xdg_data,
                               safety=safety)

    def _extend_safety(self, providers: Iterable[CacheProvider]) -> None:
        """Allowlist = default roots + every path a provider declares."""
        roots = list(default_user_roots(self.home))
        for p in providers:
            for extra in getattr(type(p), "extra_cache_roots", ()) or ():
                roots.append(self.ctx.expand(extra))
            try:
                for cp in p.cache_paths():
                    roots.append(cp.path)
            except OSError:
                continue
        self.ctx.safety = PathSafety(home=self.home, allowed_roots=roots)

    # -------------------------------------------------------------- scan
    def scan(self, progress: Optional[ProgressCb] = None) -> ScanReport:
        t0 = time.monotonic()
        log.log_event(_logger, "scan_start", home=self.home)
        report = ScanReport()

        providers = detect_all(self.ctx)
        providers.append(OtherXdgCachesProvider(
            self.ctx, claimed_cache_basenames(self.ctx, providers)))
        providers = [p for p in providers if p.detect()]
        self._extend_safety(providers)

        for p in providers:
            log.log_event(_logger, "provider_discovered", id=p.id, name=p.name)

        def measure(p: CacheProvider) -> ProviderScan:
            try:
                res = p.calculate_size()
            except Exception as exc:                       # provider bug guard
                log.log_event(_logger, "provider_measure_failed", id=p.id,
                              error=str(exc), level=40)
                report.errors.add(ErrorKind.PROVIDER_FAILURE, p.id, p.id, str(exc))
                res = None
            scan = ProviderScan(provider=p)
            if res is not None:
                scan.size_bytes = res.bytes
                scan.file_count = res.files
                scan.path_count = len(p.active_paths())
                for rec in res.errors.records:
                    rec.provider = p.id
                    report.errors.records.append(rec)
            scan.needs_elevation = bool(getattr(p, "needs_elevation", lambda: False)())
            return scan

        workers = min(8, max(2, os.cpu_count() or 4))
        done = 0
        total = max(1, len(providers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for scan in pool.map(measure, providers):
                report.scans.append(scan)
                done += 1
                if progress:
                    progress(done / total, f"Scanning {scan.provider.name}…")

        report.scans.sort(key=lambda s: s.size_bytes, reverse=True)
        report.total_bytes = sum(s.size_bytes for s in report.scans)
        report.duration = time.monotonic() - t0
        log.log_event(_logger, "scan_end", providers=len(report.scans),
                      total_bytes=report.total_bytes, seconds=round(report.duration, 3))
        return report

    # ------------------------------------------------------------- clean
    def clean(
        self,
        report: ScanReport,
        dry_run: bool = False,
        cancel: Optional[threading.Event] = None,
        progress: Optional[ProgressCb] = None,
        provider_ids: Optional[set[str]] = None,
        include_conditional: Optional[set[str]] = None,
        rescan: bool = True,
    ) -> CleanReport:
        """Clean (or dry-run plan) the providers of a previous scan.

        ``provider_ids``: restrict to specific providers (per-app cleanup).
        ``include_conditional``: ids the user explicitly approved (rule 5.1).
        """
        t0 = time.monotonic()
        include_conditional = include_conditional or set()
        out = CleanReport(dry_run=dry_run, before_bytes=report.total_bytes)
        targets = [s for s in report.scans
                   if provider_ids is None or s.provider.id in provider_ids]
        total = max(1, len(targets))
        log.log_event(_logger, "clean_start", dry_run=dry_run, providers=len(targets))

        for i, s in enumerate(targets):
            p = s.provider
            if cancel is not None and cancel.is_set():
                out.cancelled = True
                log.log_event(_logger, "clean_cancelled", at_provider=p.id)
                break
            # E-011: providers that need elevation (e.g. pacman cache) trigger
            # the polkit dialog themselves inside clean(); the engine no
            # longer pre-skips them.
            if s.needs_elevation:
                log.log_event(_logger, "provider_needs_elevation", id=p.id)
            if progress:
                progress(i / total, f"Cleaning {p.name}…")
            try:
                r = p.clean(dry_run=dry_run, cancel=cancel,
                            include_conditional=p.id in include_conditional)
            except Exception as exc:
                r = ProviderCleanResult(provider_id=p.id, attempted=True)
                r.errors.add(ErrorKind.PROVIDER_FAILURE, p.id, p.id, str(exc))
                log.log_event(_logger, "provider_clean_failed", id=p.id,
                              error=str(exc), level=40)
            out.per_provider.append(r)
            log.log_event(_logger, "provider_cleaned", id=p.id,
                          freed=r.bytes_freed, paths=r.cleaned_paths,
                          skipped=r.skipped_paths, errors=len(r.errors))
            for rec in out.per_provider[-1].errors.records:
                out.errors.records.append(rec)

        # ---- fresh measurement (rule 6): NEVER trust before-minus-removed
        if rescan and not out.cancelled:
            if progress:
                progress(0.98, "Re-measuring remaining cache…")
            fresh = self.scan()
            out.after_bytes = fresh.total_bytes
            for rec in fresh.errors.records:
                out.errors.records.append(rec)

        if progress:
            progress(1.0, "Done")
        out.duration = time.monotonic() - t0
        log.log_event(_logger, "clean_end", dry_run=dry_run,
                      cleaned=len(out.cleaned), skipped=len(out.skipped),
                      errors=len(out.failed), removed_bytes=out.removed_bytes,
                      after_bytes=out.after_bytes, seconds=round(out.duration, 3))
        return out
