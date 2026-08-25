"""Human-readable byte/quantity formatting.

Binary units (KiB/MiB/GiB) are used because that is what file managers and
`du` conventions on Linux report for cache sizes. Pure functions, no I/O.
"""

from __future__ import annotations

__all__ = ["format_bytes", "parse_size", "format_duration"]

_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def format_bytes(n: float, precision: int = 1) -> str:
    """Format a byte count as a human readable string (binary units).

    >>> format_bytes(0)
    '0 B'
    >>> format_bytes(2048)
    '2.0 KiB'
    """
    if n != n:  # NaN guard
        return "0 B"
    n = float(n)
    negative = n < 0
    n = abs(n)
    idx = 0
    while n >= 1024.0 and idx < len(_UNITS) - 1:
        n /= 1024.0
        idx += 1
    if idx == 0:
        text = f"{int(n)} {_UNITS[0]}"
    else:
        text = f"{n:.{precision}f} {_UNITS[idx]}"
    return f"-{text}" if negative else text


def parse_size(text: str) -> int:
    """Parse '1.5 GiB' / '200mb' / '1024' style strings into bytes."""
    t = text.strip().lower().replace(",", "")
    if not t:
        raise ValueError("empty size string")
    mult = 1
    for suffix, factor in (
        ("pib", 1024**5), ("tib", 1024**4), ("gib", 1024**3), ("mib", 1024**2), ("kib", 1024),
        ("pb", 1024**5), ("tb", 1024**4), ("gb", 1024**3), ("mb", 1024**2), ("kb", 1024),
        ("b", 1),
    ):
        if t.endswith(suffix):
            mult = factor
            t = t[: -len(suffix)].strip()
            break
    try:
        value = float(t)
    except ValueError as exc:
        raise ValueError(f"invalid size: {text!r}") from exc
    return int(value * mult)


def format_duration(seconds: float) -> str:
    """Format seconds as e.g. '42 s', '2 m 05 s', '1 h 03 m'."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.0f} s" if seconds >= 9.5 else f"{seconds:.1f} s"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} m"
    return f"{m} m {s:02d} s"
