"""The OS file system behind the ``FileSystem`` port (guideline G2).

Writes go through a ``<name>.tmp-<hex>`` file that is flushed and ``fsync``ed before the rename
(13.2.2). The exclusive lock is a byte-range lock on a file (``msvcrt.locking``, non-blocking),
which Windows drops when the process dies.
"""

import contextlib
import msvcrt
import ntpath
import os
import secrets
import threading
from typing import Final

from cad_application.ports import FileStat, Lock, LockHeld

_EXTENDED: Final = "\\\\?\\"
_EXTENDED_UNC: Final = "\\\\?\\UNC\\"
# Windows errors that mean "no such file" for a name that cannot exist (bad characters, too long).
_NOT_FOUND_WINERRORS: Final = frozenset({123, 161, 206, 267})


class _OsLock:
    def __init__(self, fd: int) -> None:
        self._fd: int | None = fd
        self._guard = threading.Lock()

    def release(self) -> None:
        with self._guard:
            fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            with contextlib.suppress(OSError):  # closing the handle drops the lock anyway
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # pyright: ignore[reportAttributeAccessIssue]
        finally:
            os.close(fd)


def _plain(path: str) -> str:
    """``realpath`` can return an extended-length path; the rest of the core compares plain ones."""
    if path.startswith(_EXTENDED_UNC):
        return "\\\\" + path[len(_EXTENDED_UNC) :]
    if path.startswith(_EXTENDED) and ntpath.splitdrive(path[len(_EXTENDED) :])[0]:
        return path[len(_EXTENDED) :]
    return path


def _is_missing(error: OSError) -> bool:
    if isinstance(error, FileNotFoundError | NotADirectoryError):
        return True
    return getattr(error, "winerror", None) in _NOT_FOUND_WINERRORS


class OsFileSystem:
    def resolve(self, path: str) -> str:
        real = _plain(os.path.realpath(path))
        parent = ntpath.dirname(real)
        if parent and parent != real and not os.path.isdir(parent):
            raise FileNotFoundError(real)
        return real

    def stat(self, path: str) -> FileStat | None:
        try:
            found = os.stat(path)
        except OSError as error:
            if _is_missing(error):
                return None
            raise
        is_dir = os.path.isdir(path)
        return FileStat(
            is_dir=is_dir, size=0 if is_dir else found.st_size, mtime_ns=found.st_mtime_ns
        )

    def read_bytes(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    def list_dir(self, path: str) -> tuple[str, ...]:
        return tuple(sorted(os.listdir(path)))

    def make_dirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def write_atomic(self, path: str, data: bytes) -> None:
        self._write(path, data, must_be_new=False)

    def write_new(self, path: str, data: bytes) -> None:
        self._write(path, data, must_be_new=True)

    def append_line(self, path: str, line: str) -> None:
        with open(path, "ab") as handle:
            handle.write(line.encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def remove(self, path: str) -> None:
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)

    def lock_exclusive(self, path: str) -> Lock:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_BINARY)  # pyright: ignore[reportAttributeAccessIssue]
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # pyright: ignore[reportAttributeAccessIssue]
        except OSError:
            os.close(fd)
            raise LockHeld(path) from None
        return _OsLock(fd)

    @staticmethod
    def _write(path: str, data: bytes, *, must_be_new: bool) -> None:
        tmp = f"{path}.tmp-{secrets.token_hex(4)}"
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY  # pyright: ignore[reportAttributeAccessIssue]
            with os.fdopen(os.open(tmp, flags), "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if must_be_new:
                os.rename(tmp, path)  # fails if the target exists, so a file is written once
            else:
                os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):  # the store removes it at the next open (13.2.2)
                os.remove(tmp)
            raise
