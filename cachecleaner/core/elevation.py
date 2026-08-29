"""Privilege escalation via polkit/pkexec (rule 7, E-011 fix).

Security contract (bug report §7):
* the application NEVER asks for, sees, stores, logs or forwards a password;
* authentication is performed by the system polkit agent (pkexec dialog);
* only the isolated audited helper runs elevated, never the GUI.

pkexec exit codes:
  0   → success
  126 → authentication dialog dismissed or authorization denied
  other → helper or polkit failure
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from . import log

__all__ = ["ElevationStatus", "ElevationResult", "find_helper", "run_paccache"]

_logger = log.get_logger("elevation")

_HELPER_CANDIDATES = (
    "/usr/bin/cachecleaner-paccache",     # installed package path (matches
                                           # the polkit policy annotation)
)
PKEXEC_TIMEOUT_S = 300


class ElevationStatus(Enum):
    SUCCESS = "success"
    CANCELLED = "cancelled"              # user closed/dismissed the dialog
    AUTH_FAILED = "auth_failed"          # wrong password / denied by policy
    HELPER_ERROR = "helper_error"        # helper ran but failed
    HELPER_MISSING = "helper_missing"    # package not installed properly
    LAUNCH_ERROR = "launch_error"        # pkexec unavailable / spawn failure


@dataclass
class ElevationResult:
    status: ElevationStatus
    freed_bytes: Optional[int] = None
    remaining_bytes: Optional[int] = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ElevationStatus.SUCCESS

    def user_message(self) -> str:
        return {
            ElevationStatus.SUCCESS: "Pacman cache cleaned successfully.",
            ElevationStatus.CANCELLED: "Pacman cache cleanup cancelled.",
            ElevationStatus.AUTH_FAILED: "Authentication failed. "
                                         "Pacman cache was not modified.",
            ElevationStatus.HELPER_ERROR: "Pacman cache cleanup completed "
                                          "with errors.",
            ElevationStatus.HELPER_MISSING: "The privileged helper is not "
                                            "installed (reinstall cachecleaner).",
            ElevationStatus.LAUNCH_ERROR: "Could not start the authentication "
                                          "dialog.",
        }[self.status]


def find_helper() -> Optional[str]:
    for c in _HELPER_CANDIDATES:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which("cachecleaner-paccache")   # dev-tree fallback


def _parse_helper_output(text: str) -> tuple[Optional[int], Optional[int]]:
    freed = remaining = None
    m = re.search(r"^FREED_BYTES=(\d+)$", text, re.M)
    if m:
        freed = int(m.group(1))
    m = re.search(r"^REMAINING_BYTES=(\d+)$", text, re.M)
    if m:
        remaining = int(m.group(1))
    return freed, remaining


def run_paccache(keep: int = 0,
                 pkexec: str = "pkexec",
                 helper: Optional[str] = None) -> ElevationResult:
    """Run the pacman-cache helper under polkit authentication (legacy API)."""
    return run_syscache("pacman", keep=keep, pkexec=pkexec, helper=helper)


def run_syscache(target: str,
                 keep: int = 0,
                 pkexec: str = "pkexec",
                 helper: Optional[str] = None) -> ElevationResult:
    """Run the system-cache helper for an allowlisted target under polkit.

    ``pkexec``/``helper`` are injectable for testing. The password prompt is
    drawn and handled entirely by the system polkit agent; the helper itself
    only accepts named targets (pacman|debtap), never arbitrary paths.
    """
    if target not in ("pacman", "debtap"):
        return ElevationResult(ElevationStatus.HELPER_ERROR,
                               detail=f"unknown target: {target}")
    helper = helper or find_helper()
    if not helper:
        log.log_event(_logger, "helper_missing", level=40)
        return ElevationResult(ElevationStatus.HELPER_MISSING)
    if shutil.which(pkexec) is None:
        log.log_event(_logger, "pkexec_missing", level=40)
        return ElevationResult(
            ElevationStatus.LAUNCH_ERROR,
            detail="pkexec not found — install the 'polkit' package")

    cmd = [pkexec, helper, target, str(int(keep))]
    log.log_event(_logger, "elevation_request", helper=helper, target=target,
                  keep=keep)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=PKEXEC_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        log.log_event(_logger, "elevation_timeout", level=40)
        return ElevationResult(ElevationStatus.LAUNCH_ERROR,
                               detail="authentication timed out")
    except OSError as exc:
        log.log_event(_logger, "elevation_launch_failed", error=str(exc), level=40)
        return ElevationResult(ElevationStatus.LAUNCH_ERROR, detail=str(exc))

    out = proc.stdout or ""
    err = (proc.stderr or "").strip()
    log.log_event(_logger, "elevation_result", rc=proc.returncode,
                  stdout_bytes=len(out), stderr_bytes=len(err))

    if proc.returncode == 0:
        freed, remaining = _parse_helper_output(out)
        return ElevationResult(ElevationStatus.SUCCESS, freed, remaining,
                               detail=out.strip().splitlines()[-1] if out.strip() else "")

    if proc.returncode == 126:
        # pkexec: authorization dismissed/denied. Best-effort split:
        if "dismiss" in err.lower() or not err:
            return ElevationResult(ElevationStatus.CANCELLED, detail=err)
        return ElevationResult(ElevationStatus.AUTH_FAILED, detail=err)

    return ElevationResult(ElevationStatus.HELPER_ERROR,
                           detail=err or out.strip() or f"rc={proc.returncode}")
