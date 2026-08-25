"""End-to-end CLI tests on an isolated fake home (never the real one)."""

from __future__ import annotations

import json
import os

import pytest

from cachecleaner.cli import run


def _w(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * n)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    _w(str(h / ".cache" / "pip" / "w.whl"), 10_000)
    _w(str(h / ".cache" / "appx" / "c.bin"), 5_000)
    for var in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(h))
    return h


def test_scan_text(home, capsys):
    assert run(["--home", str(home), "--scan"]) == 0
    out = capsys.readouterr().out
    assert "14.6 KiB" in out        # 15_000 bytes in binary units
    assert "lang.pip" in out


def test_scan_json(home, capsys):
    assert run(["--home", str(home), "--scan", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_bytes"] == 15_000
    ids = {p["id"] for p in data["providers"]}
    assert {"lang.pip", "xdg.other"} <= ids


def test_dry_run_keeps_files(home, capsys):
    assert run(["--home", str(home), "--dry-run", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["removed_bytes"] == 15_000
    assert (home / ".cache" / "pip" / "w.whl").exists()


def test_clean_yes_deletes_and_rescans(home, capsys):
    assert run(["--home", str(home), "--clean", "--yes", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["before_bytes"] == 15_000
    assert data["after_bytes"] == 0          # fresh scan proof
    assert data["removed_bytes"] == 15_000
    assert not (home / ".cache" / "appx" / "c.bin").exists()


def test_clean_provider_subset(home, capsys):
    assert run(["--home", str(home), "--clean", "--yes", "--json",
                "--providers", "lang.pip"]) == 0
    assert (home / ".cache" / "appx" / "c.bin").exists()
    assert not (home / ".cache" / "pip" / "w.whl").exists()


def test_clean_without_yes_aborts(home, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _="": "n")
    assert run(["--home", str(home), "--clean"]) == 0
    out = capsys.readouterr().out
    assert "Aborted" in out
    assert (home / ".cache" / "pip" / "w.whl").exists()


def test_version(capsys):
    from cachecleaner import __version__
    with pytest.raises(SystemExit) as e:
        run(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out
