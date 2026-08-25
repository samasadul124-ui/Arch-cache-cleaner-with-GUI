"""Entry point: GUI by default, CLI when flags are given or no display exists."""

from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if args:                                   # explicit flags → headless CLI
        from .cli import run
        return run(args)

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("No display detected — running a headless scan instead.\n"
              "Tip: 'cachecleaner --help' lists CLI options.")
        from .cli import run
        return run(["--scan"])

    try:
        from .gui.app import run_app
    except Exception as exc:                   # e.g. GTK missing on the system
        print(f"GUI unavailable ({exc}); falling back to a headless scan.",
              file=sys.stderr)
        from .cli import run
        return run(["--scan"])
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
