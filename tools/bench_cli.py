#!/usr/bin/env python3
"""Reproducible engine benchmarks (rule 8, 23).

Creates a synthetic cache tree in a private temp dir, then measures scan and
clean wall-time and peak RSS in-process. Nothing outside the temp dir is
touched.

    python3 tools/bench_cli.py [dirs] [files_per_dir] [file_bytes]
"""

from __future__ import annotations

import os
import resource
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cachecleaner.core.engine import Engine  # noqa: E402


def make_tree(root: str, dirs: int, files: int, size: int) -> int:
    total = 0
    data = b"x" * size
    for i in range(dirs):
        d = os.path.join(root, ".cache", f"app{i:04d}")
        os.makedirs(d, exist_ok=True)
        for j in range(files):
            with open(os.path.join(d, f"f{j:04d}.cache"), "wb") as f:
                f.write(data)
            total += size
    return total


def rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> int:
    dirs = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    files = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 8192

    tmp = tempfile.mkdtemp(prefix="cc-bench-")
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        os.environ.pop(var, None)
    os.environ["HOME"] = home

    made = make_tree(home, dirs, files, size)
    n_files = dirs * files
    print(f"fixture: {n_files} files, {made/1024/1024:.1f} MiB "
          f"in {dirs} provider-like dirs")

    rss0 = rss_mib()

    eng = Engine(home=home)
    t0 = time.perf_counter()
    report = eng.scan()
    scan_t = time.perf_counter() - t0
    rss_scan = rss_mib()

    assert report.total_bytes == made, (report.total_bytes, made)

    t0 = time.perf_counter()
    out = eng.clean(report)
    clean_t = time.perf_counter() - t0
    rss_clean = rss_mib()

    assert out.after_bytes == 0, out.after_bytes

    print(f"scan : {scan_t:7.2f} s   ({n_files/scan_t:,.0f} files/s)")
    print(f"clean: {clean_t:7.2f} s   ({n_files/clean_t:,.0f} files/s)")
    print(f"RSS  : start {rss0:.1f} MiB → after scan {rss_scan:.1f} MiB "
          f"→ after clean {rss_clean:.1f} MiB")
    print(f"correctness: before={report.total_bytes} removed={out.removed_bytes} "
          f"after={out.after_bytes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
