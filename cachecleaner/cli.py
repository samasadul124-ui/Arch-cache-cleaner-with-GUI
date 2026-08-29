"""Headless CLI: scan / dry-run / clean / JSON report.

The GUI and CLI share the same engine, so headless runs exercise the exact
production pipeline. Exit codes: 0 = clean success, 1 = partial failure or
skips with errors, 2 = fatal failure, 130 = cancelled.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading

from . import APP_NAME, __version__
from .core import log
from .core.engine import CleanReport, Engine, ScanReport
from .core.units import format_bytes

_logger = log.get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cachecleaner",
        description=f"{APP_NAME} — safe cache discovery & cleanup "
                    "(EndeavourOS / Arch Linux)")
    p.add_argument("--version", action="version",
                   version=f"{APP_NAME} {__version__}")
    p.add_argument("--home", metavar="DIR",
                   help="operate on an alternative home directory (testing)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--verbose", "-v", action="store_true")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scan", action="store_true",
                      help="scan and report cache usage (default action)")
    mode.add_argument("--dry-run", action="store_true",
                      help="report what would be deleted without deleting")
    mode.add_argument("--clean", action="store_true",
                      help="clean SAFE_CACHE providers")

    p.add_argument("--providers", metavar="IDS",
                   help="comma-separated provider ids to limit the operation")
    p.add_argument("--include-conditional", metavar="IDS",
                   help="explicitly approved CONDITIONAL_CACHE provider ids")
    p.add_argument("--yes", "-y", action="store_true",
                   help="skip the confirmation prompt for --clean")
    p.add_argument("--advanced", action="store_true",
                   help="opt-in layer-5 scan: list folders named '*cache*'")
    p.add_argument("--sweep", metavar="PATH", action="append", default=[],
                   help="explicitly select an advanced sweep path for --clean "
                        "(repeatable; implies --advanced)")
    return p


# ------------------------------------------------------------------ output
def print_scan(rep: ScanReport, as_json: bool) -> None:
    sweep_paths = []
    sw = rep.by_id("advanced.cache-name-sweep")
    if sw is not None:
        sweep_paths = [cp.path for cp in sw.provider.cache_paths()]
    if as_json:
        print(json.dumps({
            "total_bytes": rep.total_bytes,
            "advanced_sweep_paths": sweep_paths,
            "providers": [
                {"id": s.provider.id, "name": s.provider.name,
                 "category": s.provider.category.value,
                 "safety": s.provider.safety.value,
                 "size_bytes": s.size_bytes, "files": s.file_count,
                 "needs_elevation": s.needs_elevation}
                for s in rep.scans],
        }, indent=2))
        return
    print(f"\n  Detected {rep.provider_count} cache providers — "
          f"total: {format_bytes(rep.total_bytes)}\n")
    for s in rep.scans:
        flag = " [needs root]" if s.needs_elevation else ""
        print(f"  {format_bytes(s.size_bytes):>10}  {s.provider.name}{flag}")
        print(f"             id={s.provider.id}  ({s.provider.category.value})")
        if s.provider.id == "advanced.cache-name-sweep":
            for pth in sweep_paths[:100]:
                print(f"               - {pth}")
            if len(sweep_paths) > 100:
                print(f"               …and {len(sweep_paths) - 100} more")


def print_clean(out: CleanReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "dry_run": out.dry_run, "cancelled": out.cancelled,
            "before_bytes": out.before_bytes, "after_bytes": out.after_bytes,
            "removed_bytes": out.removed_bytes,
            "cleaned": [r.provider_id for r in out.cleaned],
            "skipped": [r.provider_id for r in out.skipped],
            "failed": [r.provider_id for r in out.failed],
            "errors": [{"kind": r.kind.value, "path": r.path,
                        "provider": r.provider, "count": r.count}
                       for r in out.errors.records],
        }, indent=2))
        return
    verb = "Would remove" if out.dry_run else "Removed"
    print(f"\n  Before:   {format_bytes(out.before_bytes)}")
    print(f"  {verb}: {format_bytes(out.removed_bytes)}")
    if out.after_bytes is not None:
        print(f"  Remaining (fresh scan): {format_bytes(out.after_bytes)}")
    print(f"\n  Providers cleaned: {len(out.cleaned)}   "
          f"skipped: {len(out.skipped)}   failed: {len(out.failed)}")
    if out.cancelled:
        print("  Cancelled by user.")
    if out.errors.records:
        print("\n  Errors:")
        for rec in out.errors.records[:20]:
            print(f"   - [{rec.kind.value}] {rec.path}: {rec.detail}")


def confirm() -> bool:
    try:
        answer = input("Proceed with cleanup? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


# -------------------------------------------------------------------- main
def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logfile = log.setup_logging(verbose=args.verbose)
    log.log_event(_logger, "cli_start", version=__version__,
                  scan=args.scan, dry_run=args.dry_run, clean=args.clean)

    try:
        engine = Engine(home=args.home)
    except Exception as exc:
        log.log_event(_logger, "fatal", error=str(exc), level=40)
        print(f"FATAL: cannot initialize engine: {exc}", file=sys.stderr)
        return 2

    ids = set(filter(None, (args.providers or "").split(","))) or None
    conditional = set(filter(None, (args.include_conditional or "").split(",")))

    advanced = args.advanced or bool(args.sweep)
    try:
        report = engine.scan(advanced=advanced)
    except Exception as exc:
        log.log_event(_logger, "scan_fatal", error=str(exc), level=40)
        print(f"FATAL: scan failed: {exc}", file=sys.stderr)
        return 2

    sweep_scan = report.by_id("advanced.cache-name-sweep")
    if args.sweep and sweep_scan is not None:
        sweep_scan.provider.selected = set(args.sweep)   # manual selection
        ids = {sweep_scan.provider.id}
        conditional = {sweep_scan.provider.id}

    if args.scan:
        print_scan(report, args.json)
        return 0

    if args.dry_run:
        out = engine.clean(report, dry_run=True, provider_ids=ids,
                           include_conditional=conditional)
        print_clean(out, args.json)
        return 0

    # --clean ---------------------------------------------------------------
    if not args.yes and not args.json:
        print_scan(report, False)
        if not confirm():
            print("Aborted — nothing was deleted.")
            return 0
    cancel = threading.Event()
    try:
        out = engine.clean(report, cancel=cancel, provider_ids=ids,
                           include_conditional=conditional)
    except KeyboardInterrupt:
        cancel.set()
        print("\nCancelled.", file=sys.stderr)
        return 130
    print_clean(out, args.json)
    if out.cancelled:
        return 130
    return 0 if out.ok else 1


def main() -> None:
    sys.exit(run())
