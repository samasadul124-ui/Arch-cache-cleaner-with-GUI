"""Structured logging (rule 17).

* machine-friendly `key=value` lines for the file handler (full diagnostics);
* concise human lines for the console;
* log file under ``$XDG_STATE_HOME/cachecleaner/cachecleaner.log``;
* never logs file contents, credentials or tokens — only paths and counts.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Optional

__all__ = ["setup_logging", "get_logger", "log_file_path", "log_event"]

_CONFIGURED = False


def log_file_path() -> str:
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(state, "cachecleaner", "cachecleaner.log")


class _KVFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = getattr(record, "kv", None)
        if extra:
            pairs = " ".join(f"{k}={_quote(v)}" for k, v in extra.items())
            return f"{base} {pairs}"
        return base


def _quote(v) -> str:
    s = str(v)
    if any(c in s for c in ' "\n'):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return s


def setup_logging(verbose: bool = False, logfile: Optional[str] = None) -> str:
    """Configure root 'cachecleaner' logger. Returns the log file path."""
    global _CONFIGURED
    path = logfile or log_file_path()
    root = logging.getLogger("cachecleaner")
    if _CONFIGURED:
        return path
    root.setLevel(logging.DEBUG)
    root.propagate = False

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_KVFormatter(
            fmt="ts=%(asctime)s level=%(levelname)s logger=%(name)s event=%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z"))
        root.addHandler(fh)
    except OSError as exc:                       # logging must never crash the app
        print(f"cachecleaner: cannot open log file {path}: {exc}", file=sys.stderr)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    # console gets the same structured fields as the file log, so pasted
    # terminal output carries the diagnostic numbers (freed=, errors=, …)
    ch.setFormatter(_KVFormatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(ch)
    _CONFIGURED = True
    return path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"cachecleaner.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **kv) -> None:
    """Emit a structured event line, e.g. event=scan_start providers=17."""
    logger.log(level, event, extra={"kv": kv})
