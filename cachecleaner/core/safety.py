"""Safety model: cache classification and deletion-path validation.

Nothing is ever deleted without passing :meth:`PathSafety.validate`.
The validator is deliberately conservative: when in doubt, it rejects.

Design notes
------------
* Allowed roots are compared **after realpath resolution on both sides**, so a
  legitimately symlinked cache home (e.g. ``~/.cache -> /data/cache``) still
  works, while a symlink planted *inside* the cache pointing at ``/etc`` is
  rejected because it resolves outside every allowed root.
* Deletion code (``fs.py``) only ever deletes *contents* of a validated
  directory and never follows symlinks while doing so — this module is the
  gate, ``fs.py`` is the guarded executor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

__all__ = [
    "SafetyLevel",
    "PathSafety",
    "ValidationResult",
    "DANGEROUS_PREFIXES",
    "NAME_DENYLIST",
    "default_user_roots",
]


class SafetyLevel(Enum):
    SAFE_CACHE = "safe"
    CONDITIONAL_CACHE = "conditional"
    DO_NOT_DELETE = "protected"


# Filesystem locations that must never be deleted, even partially.
DANGEROUS_PREFIXES = (
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64",
    "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/usr", "/var",
)

# Directory/file names that are never cache, even if found inside a cache root.
NAME_DENYLIST = frozenset({
    # messaging / sessions
    "tdata", "session", "sessions",
    # credentials / keys
    ".gnupg", ".ssh", ".gnome-keyring", "keyrings", "keyring", "wallet",
    "wallets", "credentials", "credentials.json", "netrc", ".netrc",
    "id_rsa", "id_ed25519", "authorized_keys", "known_hosts",
    # browser profile data (only *cache* subdirs of profiles are eligible)
    "databases", "IndexedDB", "Local Storage", "Session Storage",
    "storage", "profiles", "logins.json", "key4.db", "cert9.db",
    "cookies.sqlite", "cookies.db", "Cookies", "bookmarks",
    # misc user data
    "Documents", "Downloads", "Pictures", "Music", "Videos", "Desktop",
})

# Depth (number of path components) a deletable path must at least have.
# Prevents catastrophes from accidentally shallow roots.
MIN_COMPONENTS = 3


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def default_user_roots(home: Optional[str] = None) -> list[str]:
    """Standard per-user cache roots (XDG cache home + known tool homes)."""
    home = home or os.path.expanduser("~")
    xdg_cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(home, ".cache")
    return [
        xdg_cache,
        os.path.join(home, ".npm"),           # npm cache home default
        os.path.join(home, ".rustup", "downloads"),
        os.path.join(home, ".gradle", "caches"),
        os.path.join(home, ".m2", "repository"),  # conditional in provider, root listed for validation
    ]


class PathSafety:
    """Validates candidate deletion paths against allowed roots and denylists."""

    def __init__(
        self,
        home: Optional[str] = None,
        allowed_roots: Optional[Iterable[str]] = None,
        extra_deny_names: Iterable[str] = (),
    ) -> None:
        self.home = os.path.normpath(home or os.path.expanduser("~"))
        roots = list(allowed_roots) if allowed_roots is not None else default_user_roots(self.home)
        # normalize + resolve both sides once; keep originals for messages
        self.allowed_roots: list[str] = []
        self.allowed_real: list[str] = []
        for r in roots:
            nr = os.path.normpath(str(r))
            if nr and nr != "/" and os.path.isabs(nr):
                self.allowed_roots.append(nr)
                self.allowed_real.append(os.path.realpath(nr))
        self.deny_names = NAME_DENYLIST | frozenset(extra_deny_names)

    # ------------------------------------------------------------------ API
    def validate(self, path: str | os.PathLike) -> ValidationResult:
        """Return ValidationResult(ok, reason). Never raises."""
        try:
            return self._validate(str(path))
        except Exception as exc:  # absolute last-resort guard: refuse
            return ValidationResult(False, f"validator internal error: {exc}")

    def is_allowed_root(self, path: str) -> bool:
        p = os.path.normpath(path)
        return any(p == r or p.startswith(r + os.sep) for r in self.allowed_roots)

    # ------------------------------------------------------------- internals
    def _validate(self, raw: str) -> ValidationResult:
        s = raw.strip()
        if not s:
            return ValidationResult(False, "empty path")
        if not os.path.isabs(s):
            return ValidationResult(False, f"relative path not allowed: {raw!r}")

        p = os.path.normpath(s)
        parts = [c for c in p.split(os.sep) if c]

        if "\0" in raw:
            return ValidationResult(False, "NUL byte in path")
        if ".." in parts:
            return ValidationResult(False, f"path traversal (..): {raw!r}")

        # --- hard dangerous-prefix rejection -----------------------------
        for danger in DANGEROUS_PREFIXES:
            if p == danger:
                # exact hit on a dangerous location — only allowed when the
                # dangerous prefix itself is an explicitly allowed root
                # (e.g. /var/cache/pacman/pkg under allowed '/var/...')
                if any(p == r or p.startswith(r + os.sep) for r in self.allowed_roots):
                    break
                return ValidationResult(False, f"dangerous system path: {p}")
            if p.startswith(danger + os.sep):
                if self._inside_allowed(p):
                    break
                # /var is dangerous by default; /var/cache/pacman/pkg may be allowed
                return ValidationResult(False, f"path under protected prefix {danger}: {p}")

        # --- identity checks ------------------------------------------------
        if p == self.home:
            return ValidationResult(False, "refusing to delete $HOME itself")
        if p == "/home":
            return ValidationResult(False, "refusing to delete /home")
        if len(parts) < MIN_COMPONENTS:
            return ValidationResult(False, f"path too shallow: {p}")

        # --- denylist on every component ------------------------------------
        for part in parts:
            if part in self.deny_names:
                return ValidationResult(False, f"denied name in path: {part!r}")

        # --- containment in allowed roots (lexical) -------------------------
        if not self._inside_allowed(p):
            return ValidationResult(False, f"outside allowed cache roots: {p}")

        # --- symlink-escape check (realpath containment) --------------------
        real = os.path.realpath(p)
        if not self._inside_allowed_real(real) and not self._inside_allowed(real):
            return ValidationResult(False, f"resolves outside allowed roots: {p} -> {real}")

        return ValidationResult(True, "ok")

    def _inside_allowed(self, p: str) -> bool:
        return any(p == r or p.startswith(r + os.sep) for r in self.allowed_roots)

    def _inside_allowed_real(self, real: str) -> bool:
        return any(real == r or real.startswith(r + os.sep) for r in self.allowed_real)
