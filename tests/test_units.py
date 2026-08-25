"""Tests for cachecleaner.core.units — pure functions, no fixtures needed."""

from __future__ import annotations

import pytest

from cachecleaner.core.units import format_bytes, format_duration, parse_size


class TestFormatBytes:
    def test_zero(self):
        assert format_bytes(0) == "0 B"

    def test_bytes_no_decimals(self):
        assert format_bytes(512) == "512 B"

    def test_kib(self):
        assert format_bytes(2048) == "2.0 KiB"

    def test_mib(self):
        assert format_bytes(5 * 1024 * 1024) == "5.0 MiB"

    def test_gib_with_fraction(self):
        assert format_bytes(int(2.31 * 1024**3)) == "2.3 GiB"

    def test_large_tib(self):
        assert format_bytes(3 * 1024**4) == "3.0 TiB"

    def test_negative(self):
        assert format_bytes(-1024) == "-1.0 KiB"

    def test_nan_safe(self):
        assert format_bytes(float("nan")) == "0 B"

    def test_precision(self):
        assert format_bytes(1536, precision=2) == "1.50 KiB"


class TestParseSize:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1024", 1024),
            ("1 KiB", 1024),
            ("1.5 GiB", int(1.5 * 1024**3)),
            ("200mb", 200 * 1024**2),
            ("2,048 B", 2048),
        ],
    )
    def test_parse(self, text, expected):
        assert parse_size(text) == expected

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_size("twelve gigaparsecs")

    def test_empty(self):
        with pytest.raises(ValueError):
            parse_size("   ")


class TestFormatDuration:
    def test_sub_second(self):
        assert format_duration(0.4) == "0.4 s"

    def test_seconds(self):
        assert format_duration(42) == "42 s"

    def test_minutes(self):
        assert format_duration(125) == "2 m 05 s"

    def test_hours(self):
        assert format_duration(3780) == "1 h 03 m"

    def test_negative_clamped(self):
        assert format_duration(-5) == "0.0 s"
