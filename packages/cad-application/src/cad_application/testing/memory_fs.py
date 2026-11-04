"""An in-memory FileSystem with Windows semantics and crash simulation (guideline G2).

Paths are case-insensitive and case-preserving, accept ``/`` and ``\\``, and may pass through
junctions. Every mutation counts as "write", "fsync" and "rename" steps; ``fail_at=(kind, n)``
raises ``SimulatedCrash`` at the nth step of that kind, leaving the state a real crash would.
"""

import ntpath
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from cad_application.ports import FileStat, LockHeld

type StepKind = Literal["write", "fsync", "rename"]
type FaultPoint = tuple[StepKind, int]

_MAX_HOPS: Final = 32
_MTIME_STEP_NS: Final = 1000


class SimulatedCrash(Exception):  # noqa: N818 - a crash, not an error to handle
    """The process 'died' at a fault point."""


@dataclass(slots=True)
class _Node:
    name: str
    is_dir: bool
    data: bytes = b""
    mtime_ns: int = 0


class _MemoryLock:
    def __init__(self, fs: "MemoryFileSystem", key: str) -> None:
        self._fs = fs
        self._key = key

    def release(self) -> None:
        self._fs.release_lock(self._key)


def _key(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path))


def _is_root(path: str) -> bool:
    drive, rest = ntpath.splitdrive(ntpath.normpath(path))
    return bool(drive) and rest in ("", "\\")


class MemoryFileSystem:
    """The test file system. One lock table per instance, shared by every store on it."""

    def __init__(
        self, junctions: Mapping[str, str] | None = None, fail_at: FaultPoint | None = None
    ) -> None:
        self._guard = threading.RLock()
        self._junctions = {_key(link): ntpath.normpath(t) for link, t in (junctions or {}).items()}
        self._nodes: dict[str, _Node] = {}
        self._locks: set[str] = set()
        self._fail_at = fail_at
        self._counts: dict[str, int] = {"write": 0, "fsync": 0, "rename": 0}
        self._tick = 0
        self._tmp = 0

    # --- path handling -------------------------------------------------------------------

    def _real(self, path: str, hops: int = 0) -> str:
        """The path with junctions followed and stored case applied; no existence checks."""
        if hops > _MAX_HOPS:
            raise OSError("too many levels of junctions")
        norm = ntpath.normpath(path)
        drive, rest = ntpath.splitdrive(norm)
        if not ntpath.isabs(norm) or not drive:
            raise ValueError(f"not an absolute path: {path!r}")
        current = (drive.upper() if len(drive) == 2 else drive) + "\\"  # noqa: PLR2004
        for part in (p for p in rest.split("\\") if p):
            candidate = ntpath.join(current, part)
            target = self._junctions.get(_key(candidate))
            if target is not None:
                current = self._real(target, hops + 1)
                continue
            node = self._nodes.get(_key(candidate))
            current = ntpath.join(current, node.name if node else part)
        return current

    def _dir_exists(self, real: str) -> bool:
        if _is_root(real):
            return True
        node = self._nodes.get(_key(real))
        return node is not None and node.is_dir

    def _parent_checked(self, real: str) -> None:
        if not self._dir_exists(ntpath.dirname(real)):
            raise FileNotFoundError(real)

    def _touch(self, node: _Node) -> None:
        self._tick += 1
        node.mtime_ns = self._tick * _MTIME_STEP_NS

    def _step(self, kind: StepKind) -> bool:
        """Count a step; True when the fault fires here (one-shot)."""
        self._counts[kind] += 1
        if self._fail_at == (kind, self._counts[kind]):
            self._fail_at = None
            return True
        return False

    # --- reads ---------------------------------------------------------------------------

    def resolve(self, path: str) -> str:
        with self._guard:
            real = self._real(path)
            self._parent_checked(real)
            return real

    def stat(self, path: str) -> FileStat | None:
        with self._guard:
            real = self._real(path)
            if _is_root(real):
                return FileStat(True, 0, 0)
            node = self._nodes.get(_key(real))
            if node is None:
                return None
            return FileStat(node.is_dir, 0 if node.is_dir else len(node.data), node.mtime_ns)

    def read_bytes(self, path: str) -> bytes:
        with self._guard:
            real = self._real(path)
            node = self._nodes.get(_key(real))
            if node is None:
                raise FileNotFoundError(real)
            if node.is_dir:
                raise IsADirectoryError(real)
            return node.data

    def list_dir(self, path: str) -> tuple[str, ...]:
        with self._guard:
            real = self._real(path)
            if not self._dir_exists(real):
                raise FileNotFoundError(real)
            parent = _key(real)
            names = [n.name for k, n in self._nodes.items() if _key(ntpath.dirname(k)) == parent]
            return tuple(sorted(names))

    # --- writes --------------------------------------------------------------------------

    def make_dirs(self, path: str) -> None:
        with self._guard:
            real = self._real(path)
            missing: list[str] = []
            current = real
            while not self._dir_exists(current):
                missing.append(current)
                current = ntpath.dirname(current)
            for folder in reversed(missing):
                if (node := self._nodes.get(_key(folder))) is not None and not node.is_dir:
                    raise FileExistsError(folder)
                node = _Node(ntpath.basename(folder), True)
                self._touch(node)
                self._nodes[_key(folder)] = node

    def _tmp_path(self, real: str) -> str:
        self._tmp += 1
        return ntpath.join(ntpath.dirname(real), f"{ntpath.basename(real)}.tmp-{self._tmp:08x}")

    def _write_via_tmp(self, real: str, data: bytes, *, must_be_new: bool) -> None:
        self._parent_checked(real)
        existing = self._nodes.get(_key(real))
        if existing is not None and (existing.is_dir or must_be_new):
            raise FileExistsError(real) if must_be_new else IsADirectoryError(real)
        tmp = self._tmp_path(real)
        tmp_node = _Node(ntpath.basename(tmp), False)
        self._nodes[_key(tmp)] = tmp_node
        if self._step("write"):
            tmp_node.data = data[: len(data) // 2]  # a torn temporary file
            self._touch(tmp_node)
            raise SimulatedCrash("write")
        tmp_node.data = data
        self._touch(tmp_node)
        if self._step("fsync"):
            raise SimulatedCrash("fsync")
        if self._step("rename"):
            raise SimulatedCrash("rename")  # rename is atomic: the target is still the old one
        del self._nodes[_key(tmp)]
        target = self._nodes.get(_key(real))
        if must_be_new and target is not None:
            raise FileExistsError(real)
        node = target or _Node(ntpath.basename(real), False)
        node.data = data
        self._touch(node)
        self._nodes[_key(real)] = node

    def write_atomic(self, path: str, data: bytes) -> None:
        with self._guard:
            self._write_via_tmp(self._real(path), data, must_be_new=False)

    def write_new(self, path: str, data: bytes) -> None:
        with self._guard:
            self._write_via_tmp(self._real(path), data, must_be_new=True)

    def append_line(self, path: str, line: str) -> None:
        with self._guard:
            real = self._real(path)
            self._parent_checked(real)
            node = self._nodes.get(_key(real))
            if node is not None and node.is_dir:
                raise IsADirectoryError(real)
            if node is None:
                node = _Node(ntpath.basename(real), False)
                self._nodes[_key(real)] = node
            payload = line.encode("utf-8") + b"\n"
            if self._step("write"):
                node.data += payload[: max(1, len(payload) // 2)]  # a torn last line
                self._touch(node)
                raise SimulatedCrash("write")
            node.data += payload
            self._touch(node)
            if self._step("fsync"):
                raise SimulatedCrash("fsync")

    def remove(self, path: str) -> None:
        with self._guard:
            real = self._real(path)
            node = self._nodes.get(_key(real))
            if node is None:
                raise FileNotFoundError(real)
            if node.is_dir and self.list_dir(real):
                raise OSError(f"folder not empty: {real}")
            del self._nodes[_key(real)]

    # --- locks ---------------------------------------------------------------------------

    def lock_exclusive(self, path: str) -> _MemoryLock:
        with self._guard:
            real = self._real(path)
            self._parent_checked(real)
            key = _key(real)
            if key in self._locks:
                raise LockHeld(real)
            if key not in self._nodes:
                node = _Node(ntpath.basename(real), False)
                self._touch(node)
                self._nodes[key] = node
            self._locks.add(key)
            return _MemoryLock(self, key)

    def release_lock(self, key: str) -> None:
        with self._guard:
            self._locks.discard(key)

    def drop_locks(self) -> None:
        """Simulate the death of the process that held every lock."""
        with self._guard:
            self._locks.clear()
