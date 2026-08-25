"""Packaging regression tests (bug report §9, E-010).

makepkg itself only runs on Arch, so these tests verify everything that CAN be
verified elsewhere: PKGBUILD syntax, version coupling, and — critically — that
the source directory used by build()/package() matches the directory GitHub
archives actually extract to ("<repo>-<version>", independent of pkgname).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKGBUILD = os.path.join(REPO, "packaging", "PKGBUILD")


def _pkgbuild() -> str:
    with open(PKGBUILD) as f:
        return f.read()


def _get(text: str, key: str) -> str:
    m = re.search(rf"^{key}=('([^']*)'|\"([^\"]*)\"|(\S+))\s*$", text, re.M)
    assert m, f"{key} not found in PKGBUILD"
    return m.group(2) or m.group(3) or m.group(4)


class TestPkgbuildBasics:
    def test_syntax(self):
        if shutil.which("bash") is None:
            pytest.skip("bash unavailable")
        r = subprocess.run(["bash", "-n", PKGBUILD], capture_output=True)
        assert r.returncode == 0, r.stderr.decode()

    def test_version_matches_package(self):
        from cachecleaner import __version__
        assert _get(_pkgbuild(), "pkgver") == __version__

    def test_pkgname_and_srcrepo(self):
        text = _pkgbuild()
        assert _get(text, "pkgname") == "cachecleaner"
        m = re.search(r"^_srcrepo=(\S+)", text, re.M)
        assert m and m.group(1) == "cache-cleaner", \
            "_srcrepo must name the GitHub repo (hyphenated)"


class TestSourceDirCoupling:
    """E-010 regression: cd-target must equal the GitHub extraction dir."""

    def test_cd_targets_match_github_archive_convention(self):
        text = _pkgbuild()
        srcrepo = re.search(r"^_srcrepo=(\S+)", text, re.M).group(1)
        pkgver = _get(text, "pkgver")
        # GitHub archives extract to <repo>-<version>
        github_dir = f"{srcrepo}-{pkgver}"
        # repo name in the source URL must equal _srcrepo ($url expanded)
        src_line = re.search(r'^source=\((.*)\)$', text, re.M).group(1)
        src_line = src_line.replace("$url", _get(text, "url")) \
                           .replace("$pkgver", pkgver)
        url_m = re.search(r"/([^/]+)/archive/refs/tags/", src_line)
        assert url_m and url_m.group(1) == srcrepo, \
            "source URL repo must equal _srcrepo"
        # every cd in build()/package() must land on the real extraction dir
        cds = re.findall(r'cd "([^"]+)"', text)
        assert cds, "PKGBUILD has no cd statements?"
        for cd in cds:
            expanded = cd.replace("$_srcrepo", srcrepo).replace("$pkgver", pkgver)
            assert expanded == f"$srcdir/{github_dir}", \
                f"cd {cd!r} resolves to {expanded!r}, not $srcdir/{github_dir}"

    def test_no_pkgname_coupled_cd(self):
        # the exact E-010 anti-pattern must never return
        assert 'cd "$pkgname-$pkgver"' not in _pkgbuild()


class TestInstalledFilesExist:
    @pytest.mark.parametrize("rel", [
        "data/cachecleaner.desktop",
        "data/icons/hicolor/scalable/apps/cachecleaner.svg",
        "packaging/cachecleaner-paccache",
        "packaging/io.github.cachecleaner.paccache.policy",
        "README.md",
        "pyproject.toml",
    ])
    def test_present(self, rel):
        assert os.path.isfile(os.path.join(REPO, rel)), rel
