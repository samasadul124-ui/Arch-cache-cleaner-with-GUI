"""Advanced manual sweep provider (feature: 'delete folders named *cache*
only when I select them').

Nothing here ever runs by default:
* the engine only instantiates it in advanced mode;
* clean() deletes ONLY the paths present in ``self.selected`` (populated by
  the GUI checkboxes / CLI --sweep), each re-validated and re-checked for the
  '*cache*' name right before deletion;
* class attribute ``manual_selection_only`` keeps it out of Clean All and the
  Include-checkbox flow entirely.
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional

from ..core import sweep
from ..core.errors import ErrorKind
from ..core.fs import delete_contents, dir_size
from ..core.provider import (CachePath, CacheProvider, Category,
                             ProviderCleanResult)
from ..core.safety import PathSafety, SafetyLevel

__all__ = ["CacheNameSweepProvider"]


class CacheNameSweepProvider(CacheProvider):
    id = "advanced.cache-name-sweep"
    name = "Folders named '*cache*' (advanced)"
    category = Category.SYSTEM
    safety = SafetyLevel.CONDITIONAL_CACHE
    manual_selection_only = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.selected: set[str] = set()          # UI/CLI populate this
        self._validator = PathSafety(home=ctx.home, allowed_roots=[ctx.home])
        self._found: Optional[list[str]] = None

    # ------------------------------------------------------------ discovery
    def cache_paths(self) -> list[CachePath]:
        if self._found is None:
            self._found = sweep.find_cache_named_dirs(
                self.ctx.home, validator=self._validator)
        return [CachePath(p, f"directory named '{os.path.basename(p)}'",
                          SafetyLevel.CONDITIONAL_CACHE)
                for p in self._found]

    def detect(self) -> bool:
        return bool(self.cache_paths())

    def explain(self) -> str:
        return ("Advanced sweep: every folder in your home whose name "
                "contains 'cache'. Nothing is deleted unless you tick it "
                "yourself. Review each entry — some may belong to apps that "
                "recreate them slowly.")

    # -------------------------------------------------------------- cleaning
    def clean(
        self,
        dry_run: bool = False,
        cancel: Optional[threading.Event] = None,
        progress: Optional[Callable[[int, int], None]] = None,
        include_conditional: bool = False,
    ) -> ProviderCleanResult:
        res = ProviderCleanResult(provider_id=self.id, attempted=True)
        found = {cp.path for cp in self.cache_paths()}
        res.skipped_paths = len(found - self.selected)

        # selection-driven: every selected path is re-validated right here,
        # so CLI-injected paths get the same gates as GUI ticked ones
        for path in sorted(self.selected):
            if cancel is not None and cancel.is_set():
                res.cancelled = True
                break
            # belt & braces: re-check name + validation right before deleting
            if not sweep.name_is_cache_like(os.path.basename(path)):
                res.errors.add(ErrorKind.INVALID_PATH, path, self.id,
                               "name does not match '*cache*' — skipped")
                continue
            verdict = self._validator.validate(path)
            if not verdict.ok:
                res.errors.add(ErrorKind.INVALID_PATH, path, self.id,
                               verdict.reason)
                continue
            if not os.path.isdir(path):
                res.errors.add(ErrorKind.PATH_VANISHED, path, self.id,
                               "vanished before clean")
                continue
            before = dir_size(path).bytes
            dr = delete_contents(path, self._validator, dry_run=dry_run,
                                 cancel=cancel)
            if dr.refused:
                res.errors.add(ErrorKind.INVALID_PATH, path, self.id,
                               dr.refuse_reason)
                continue
            res.cleaned_paths += 1
            res.bytes_freed += dr.bytes_freed if not dry_run else before
            for rec in dr.errors.records:
                rec.provider = self.id
                res.errors.records.append(rec)
        return res
