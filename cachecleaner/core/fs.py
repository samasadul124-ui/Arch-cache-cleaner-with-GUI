"""Streaming filesystem measurement and deletion.

Rules implemented here
----------------------
* Sizes are **measured**, never estimated — via ``lstat`` while traversing.
* File contents are never read (no RAM growth with file size).
* Traversal is iterative (explicit stack) — no recursion limit on huge trees.
* Symlinks are never followed: size uses ``lstat``; deletion ``unlink``s the
  link itself, so a link pointing outside the cache root cannot drag external
  data into the operation.
* Vanishing files, permission errors and broken links are classified and
  accumulated, never fatal.
* ``delete_contents`` removes only the *contents* of a validated root and
  keeps the root directory itself (applications expect their cache dir to
  exist).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from .errors import ErrorBucket, ErrorKind, classify
from .safety import PathSafety

__all__ = ["SizeResult", "DeleteResult", "dir_size", "delete_contents"]

# progress callback cadence (avoid per-file Python callback overhead)
_PROGRESS_EVERY = 256


@dataclass
class SizeResult:
    bytes: int = 0
    files: int = 0
    dirs: int = 0
    symlinks: int = 0
    errors: ErrorBucket = field(default_factory=ErrorBucket)

    @property
    def ok(self) -> bool:
        return True  # partial results are still valid measurements


@dataclass
class DeleteResult:
    bytes_freed: int = 0
    files_deleted: int = 0
    dirs_deleted: int = 0
    links_deleted: int = 0
    cancelled: bool = False
    refused: bool = False           # safety validator rejected the root
    refuse_reason: str = ""
    errors: ErrorBucket = field(default_factory=ErrorBucket)

    @property
    def total_deleted(self) -> int:
        return self.files_deleted + self.dirs_deleted + self.links_deleted


def dir_size(path: str | os.PathLike, errors: Optional[ErrorBucket] = None) -> SizeResult:
    """Measure the size of ``path`` (recursive) without reading file bodies.

    Counts regular-file sizes via lstat. Symlink targets are not counted.
    Inaccessible subtrees are recorded as errors and skipped.
    """
    path = os.fspath(path)
    res = SizeResult()
    errbuf = errors if errors is not None else res.errors

    if not os.path.lexists(path):
        errbuf.add(ErrorKind.PATH_VANISHED, path, detail="path does not exist")
        return res

    stack = [path]
    while stack:
        current = stack.pop()
        try:
            it = os.scandir(current)
        except OSError as exc:
            errbuf.add(classify(exc, current), current, detail=str(exc))
            continue
        with it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        res.symlinks += 1
                        try:
                            res.bytes += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            pass  # broken link — lstat may still fail on some fs
                    elif entry.is_dir(follow_symlinks=False):
                        res.dirs += 1
                        stack.append(entry.path)
                    else:
                        res.files += 1
                        res.bytes += entry.stat(follow_symlinks=False).st_size
                except FileNotFoundError:
                    errbuf.add(ErrorKind.PATH_VANISHED, entry.path,
                               detail="vanished during scan")
                except OSError as exc:
                    errbuf.add(classify(exc, entry.path), entry.path, detail=str(exc))
    return res


def delete_contents(
    root: str | os.PathLike,
    safety: PathSafety,
    dry_run: bool = False,
    cancel: Optional[threading.Event] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    progress_every: int = _PROGRESS_EVERY,
) -> DeleteResult:
    """Delete everything *inside* ``root`` (root itself is kept).

    ``root`` must pass ``safety.validate``; otherwise the call is refused and
    nothing is touched. With ``dry_run=True`` the same traversal runs but no
    filesystem mutation happens; counters describe what *would* be removed.
    """
    root = os.fspath(root)
    res = DeleteResult()

    verdict = safety.validate(root)
    if not verdict.ok:
        res.refused = True
        res.refuse_reason = verdict.reason
        res.errors.add(ErrorKind.INVALID_PATH, root, detail=verdict.reason)
        return res

    if not os.path.isdir(root):
        res.refused = True
        res.refuse_reason = "not a directory"
        res.errors.add(ErrorKind.PATH_VANISHED, root, detail="root missing or not a dir")
        return res

    def _cancelled() -> bool:
        return cancel is not None and cancel.is_set()

    ops_since_report = 0
    cadence = max(1, int(progress_every))

    def _report() -> None:
        nonlocal ops_since_report
        if progress is not None:
            ops_since_report += 1
            if ops_since_report >= cadence:
                ops_since_report = 0
                progress(res.total_deleted, res.bytes_freed)

    # ------------------------------------------------------------------ walk
    # Post-order iterative traversal: collect dir order, delete files on the
    # way down, dirs on the way back up.
    dir_stack: list[str] = [root]
    dirs_post_order: list[str] = []

    # phase 1: delete files/symlinks, record subdirectories
    idx = 0
    while idx < len(dir_stack):
        if _cancelled():
            res.cancelled = True
            break
        current = dir_stack[idx]
        idx += 1
        if current != root:
            dirs_post_order.append(current)
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            res.errors.add(classify(exc, current), current, detail=str(exc))
            continue
        for entry in entries:
            if _cancelled():
                res.cancelled = True
                break
            p = entry.path
            try:
                if entry.is_symlink():
                    size = _safe_size(entry)
                    if not dry_run:
                        os.unlink(p)          # never follows the link
                    res.links_deleted += 1
                    res.bytes_freed += size
                elif entry.is_dir(follow_symlinks=False):
                    dir_stack.append(p)
                    continue
                else:
                    size = _safe_size(entry)
                    if not dry_run:
                        os.unlink(p)
                    res.files_deleted += 1
                    res.bytes_freed += size
            except FileNotFoundError:
                res.errors.add(ErrorKind.PATH_VANISHED, p, detail="vanished during clean")
            except OSError as exc:
                res.errors.add(classify(exc, p), p, detail=str(exc))
            _report()

    # phase 2: remove empty directories deepest-first (root excluded)
    if not res.cancelled:
        for d in reversed(dirs_post_order):
            if _cancelled():
                res.cancelled = True
                break
            try:
                if not dry_run:
                    os.rmdir(d)
                res.dirs_deleted += 1
            except FileNotFoundError:
                res.errors.add(ErrorKind.PATH_VANISHED, d, detail="vanished during clean")
            except OSError as exc:
                # non-empty dir (e.g. a locked file inside) — classify & keep going
                res.errors.add(classify(exc, d), d, detail=str(exc))
            _report()

    if progress is not None:
        progress(res.total_deleted, res.bytes_freed)
    return res


def _safe_size(entry: os.DirEntry) -> int:
    try:
        return entry.stat(follow_symlinks=False).st_size
    except OSError:
        return 0
