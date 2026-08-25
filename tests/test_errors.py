"""Tests for error classification and the ErrorBucket accumulator."""

from __future__ import annotations

import errno
import os

import pytest

from cachecleaner.core.errors import (
    CleanError,
    ErrorBucket,
    ErrorKind,
    classify,
    user_message,
)


class TestClassify:
    def test_permission_error(self):
        assert classify(PermissionError("denied"), "/x") is ErrorKind.PERMISSION_DENIED

    def test_eacces_errno(self):
        e = OSError(errno.EACCES, "Permission denied")
        assert classify(e, "/x") is ErrorKind.PERMISSION_DENIED

    def test_enoent_plain_file(self, tmp_path):
        assert classify(FileNotFoundError(), str(tmp_path / "gone")) is ErrorKind.PATH_VANISHED

    def test_enoent_broken_symlink(self, tmp_path):
        link = tmp_path / "broken"
        os.symlink(tmp_path / "target-does-not-exist", link)
        assert classify(FileNotFoundError(), str(link)) is ErrorKind.BROKEN_SYMLINK

    def test_ebusy(self):
        e = OSError(errno.EBUSY, "busy")
        assert classify(e, "/x") is ErrorKind.FILE_IN_USE

    def test_eloop(self):
        e = OSError(errno.ELOOP, "loop")
        assert classify(e, "/x") is ErrorKind.BROKEN_SYMLINK

    def test_enotdir(self):
        e = OSError(errno.ENOTDIR, "not a dir")
        assert classify(e, "/x") is ErrorKind.INVALID_PATH

    def test_generic_oserror(self):
        e = OSError(errno.EIO, "io problem")
        assert classify(e, "/x") is ErrorKind.FILESYSTEM_ERROR

    def test_keyboard_interrupt(self):
        assert classify(KeyboardInterrupt(), "/x") is ErrorKind.CANCELLED

    def test_value_error(self):
        assert classify(ValueError("bad"), "/x") is ErrorKind.UNKNOWN

    def test_clean_error_passthrough(self):
        ce = CleanError(ErrorKind.PROVIDER_FAILURE, "/p", "boom")
        assert classify(ce, "/p") is ErrorKind.PROVIDER_FAILURE


class TestUserMessages:
    @pytest.mark.parametrize("kind", list(ErrorKind))
    def test_every_kind_has_message(self, kind):
        msg = user_message(kind)
        assert isinstance(msg, str) and len(msg) > 5


class TestErrorBucket:
    def test_collapse_repeats(self):
        b = ErrorBucket()
        for _ in range(3):
            b.add(ErrorKind.PERMISSION_DENIED, "/a/b", provider="x")
        assert len(b) == 3
        assert len(b.records) == 1
        assert b.records[0].count == 3

    def test_add_exception(self):
        b = ErrorBucket()
        kind = b.add_exception(PermissionError("denied"), "/a/b", provider="npm")
        assert kind is ErrorKind.PERMISSION_DENIED
        assert b.records[0].provider == "npm"

    def test_summary(self):
        b = ErrorBucket()
        b.add(ErrorKind.PERMISSION_DENIED, "/a")
        b.add(ErrorKind.PERMISSION_DENIED, "/a")
        b.add(ErrorKind.PATH_VANISHED, "/b")
        assert b.summary() == {"permission_denied": 2, "path_vanished": 1}
