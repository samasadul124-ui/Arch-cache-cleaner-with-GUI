"""Layer-5 advanced discovery (opt-in): directories whose NAME contains
'cache' (case-insensitive) inside the user's home.

Hard safety posture (this is a manual-selection sweep, never automatic):
* only runs when the user explicitly enables it (GUI toggle / --advanced);
* never a full-disk scan: bounded to $HOME, max depth, pruned heavy trees;
* symlinked directories are neither followed nor listed (escape defence);
* every candidate still passes the PathSafety validator (denylist names,
  realpath containment, depth, dangerous-prefix rules);
* results are only ever deleted as CONDITIONAL data with explicit per-entry
  user selection (providers/sweep.py).
"""

from __future__ import annotations

import os
from typing import Iterator, Optional

from .safety import NAME_DENYLIST, PathSafety

__all__ = ["find_cache_named_dirs", "name_is_cache_like"]

#: trees where '*cache*' dirs are build artefacts/noise — never swept
PRUNE_DIRS = frozenset({".git", "node_modules", ".svn", "hg", ".hg"})
MAX_DEPTH = 6
MAX_RESULTS = 500


def name_is_cache_like(name: str) -> bool:
    return "cache" in name.lower()


def _validator(home: str) -> PathSafety:
    # the user's home is the ONLY root this sweep may ever touch
    return PathSafety(home=home, allowed_roots=[home])


def _contains_denied_child(path: str) -> bool:
    """A candidate whose immediate children include denylisted names
    (tdata, keyring, …) is never offered — deleting it would destroy
    protected data along with the cache."""
    try:
        for e in os.scandir(path):
            if e.name in NAME_DENYLIST:
                return True
    except OSError:
        pass
    return False


def find_cache_named_dirs(
    home: str,
    max_depth: int = MAX_DEPTH,
    validator: Optional[PathSafety] = None,
) -> list[str]:
    """Return validated directories under ``home`` whose name contains
    'cache', sorted, capped at MAX_RESULTS. Iterative, symlink-safe."""
    home = os.path.normpath(home)
    val = validator or _validator(home)
    out: list[str] = []
    stack: list[tuple[str, int]] = [(home, 0)]

    while stack and len(out) < MAX_RESULTS:
        current, depth = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            try:
                if entry.is_symlink():
                    continue                      # never follow, never list
                if entry.is_dir(follow_symlinks=False):
                    if name in PRUNE_DIRS or name in NAME_DENYLIST:
                        continue
                    if depth + 1 < max_depth:
                        stack.append((entry.path, depth + 1))
                    if name_is_cache_like(name) and name not in NAME_DENYLIST:
                        if _contains_denied_child(entry.path):
                            continue
                        verdict = val.validate(entry.path)
                        if verdict.ok:
                            out.append(entry.path)
            except OSError:
                continue
    return sorted(out)[:MAX_RESULTS]
