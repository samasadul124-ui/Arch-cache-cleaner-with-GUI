"""Classified error handling.

Every error surfaced by the scanner or cleaning engine is funnelled through
:class:`CleanError` / :func:`classify` so the UI can show a concise reason and
the log keeps full diagnostics. No error is ever swallowed silently.
"""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

__all__ = ["ErrorKind", "CleanError", "ErrorRecord", "classify", "user_message"]


class ErrorKind(Enum):
    PERMISSION_DENIED = "permission_denied"
    PATH_VANISHED = "path_vanished"
    FILE_IN_USE = "file_in_use"
    INVALID_PATH = "invalid_path"
    BROKEN_SYMLINK = "broken_symlink"
    INSUFFICIENT_PRIVILEGES = "insufficient_privileges"  # needs elevation (root)
    FILESYSTEM_ERROR = "filesystem_error"
    PROVIDER_FAILURE = "provider_failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


_USER_MESSAGES = {
    ErrorKind.PERMISSION_DENIED: "Permission denied — this user may not delete the item.",
    ErrorKind.PATH_VANISHED: "The file or directory disappeared while it was being processed.",
    ErrorKind.FILE_IN_USE: "The file is currently in use by another program.",
    ErrorKind.INVALID_PATH: "The path is invalid and was skipped for safety.",
    ErrorKind.BROKEN_SYMLINK: "A broken symbolic link was encountered.",
    ErrorKind.INSUFFICIENT_PRIVILEGES: "Administrator privileges are required for this location.",
    ErrorKind.FILESYSTEM_ERROR: "A filesystem error occurred.",
    ErrorKind.PROVIDER_FAILURE: "The cache provider failed internally.",
    ErrorKind.CANCELLED: "The operation was cancelled.",
    ErrorKind.UNKNOWN: "An unexpected error occurred.",
}


class CleanError(Exception):
    """Raised/recorded for a single failed path or provider step."""

    def __init__(self, kind: ErrorKind, path: str, detail: str = "",
                 provider: str = "", original: Optional[BaseException] = None):
        self.kind = kind
        self.path = path
        self.detail = detail
        self.provider = provider
        self.original = original
        super().__init__(f"[{kind.value}] {path}: {detail}")


@dataclass
class ErrorRecord:
    """One classified error for reports/logs."""

    kind: ErrorKind
    path: str
    provider: str
    detail: str = ""
    count: int = 1

    def user_text(self) -> str:
        return f"{user_message(self.kind)} ({os.path.basename(self.path) or self.path})"


def classify(exc: BaseException, path: str = "") -> ErrorKind:
    """Map an exception raised during filesystem work to an ErrorKind."""
    if isinstance(exc, CleanError):
        return exc.kind
    if isinstance(exc, KeyboardInterrupt):
        return ErrorKind.CANCELLED
    if isinstance(exc, PermissionError):
        return ErrorKind.PERMISSION_DENIED
    if isinstance(exc, FileNotFoundError):
        return ErrorKind.BROKEN_SYMLINK if os.path.islink(path) else ErrorKind.PATH_VANISHED
    if isinstance(exc, OSError):
        err = exc.errno
        if err in (errno.EACCES, errno.EPERM):
            return ErrorKind.PERMISSION_DENIED
        if err == errno.ENOENT:
            return ErrorKind.PATH_VANISHED
        if err in (errno.EBUSY, errno.ETXTBSY):
            return ErrorKind.FILE_IN_USE
        if err == errno.ELOOP:
            return ErrorKind.BROKEN_SYMLINK
        if err in (errno.ENOTDIR, errno.EINVAL, errno.ENAMETOOLONG, errno.EISDIR, errno.ENOTEMPTY):
            return ErrorKind.INVALID_PATH
        return ErrorKind.FILESYSTEM_ERROR
    return ErrorKind.UNKNOWN


def user_message(kind: ErrorKind) -> str:
    return _USER_MESSAGES.get(kind, _USER_MESSAGES[ErrorKind.UNKNOWN])


@dataclass
class ErrorBucket:
    """Accumulates ErrorRecords, collapsing repeats of the same kind+provider."""

    records: list[ErrorRecord] = field(default_factory=list)

    def add(self, kind: ErrorKind, path: str, provider: str = "", detail: str = "") -> None:
        for rec in self.records:
            if rec.kind == kind and rec.provider == provider and rec.path == path:
                rec.count += 1
                return
        self.records.append(ErrorRecord(kind=kind, path=path, provider=provider, detail=detail))

    def add_exception(self, exc: BaseException, path: str, provider: str = "") -> ErrorKind:
        kind = classify(exc, path)
        self.add(kind, path, provider, detail=str(exc))
        return kind

    def __len__(self) -> int:
        return sum(r.count for r in self.records)

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in self.records:
            out[rec.kind.value] = out.get(rec.kind.value, 0) + rec.count
        return out
