"""A small cross-process exclusive lock on a sidecar file (spec 010 Amendment A, R9-R10).

`msvcrt.locking` on Windows, `fcntl.flock` elsewhere: standard library only. The lock is an OS advisory
lock held through an open handle, so the OS releases it when the handle closes, including when the process
dies. The lock file is never written to; its existence alone never means "locked".
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # one byte at offset 0; may lie past the end of the file
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


POLL_SECONDS = 0.01
MAX_POLL_SECONDS = 0.05


class LockTimeout(TimeoutError):
    """The lock was not acquired before the deadline."""


@contextmanager
def file_lock(path: str | Path, timeout: float) -> Iterator[None]:
    """Hold an exclusive lock on `path` (created empty if missing), retrying without blocking until `timeout`."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        delay = POLL_SECONDS
        while not _try_lock(fd):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LockTimeout(f"lock not acquired within {timeout:g} s")
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, MAX_POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
