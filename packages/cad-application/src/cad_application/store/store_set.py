"""StoreSet: the stores a core service has open, and the known-stores list (spec 13.2.1)."""

import ntpath
import threading
from collections.abc import Callable
from dataclasses import dataclass

from cad_ir.core.json_types import JsonValue

from cad_application.paths import Authorized
from cad_application.ports import Clock, FileSystem
from cad_application.store.codec import decode_json, encode
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore


@dataclass(frozen=True, slots=True)
class KnownStore:
    store_dir: str
    project_root: str


class StoreSet:
    """Opens each store once. An unreadable known-stores list is treated as empty (it is a
    cache of folders, rewritten on the next open); a store that cannot be opened is skipped.

    ``on_first_open(store, project_root)`` runs for a store opened by ``open_for`` for the first
    time, before anything can see it: recovery of a store that was not listed at start (13.2.3).
    Stores opened by ``open_known`` are left to the caller, which recovers them as a group."""

    def __init__(self, fs: FileSystem, clock: Clock, known_stores_path: str) -> None:
        self._fs = fs
        self._clock = clock
        self._known_path = known_stores_path
        self._open: dict[str, FileStore] = {}
        self._roots: dict[str, str] = {}
        self._on_first_open: Callable[[FileStore, str], object] | None = None
        self._guard = threading.RLock()

    def set_on_first_open(self, hook: Callable[[FileStore, str], object]) -> None:
        self._on_first_open = hook

    @property
    def fs(self) -> FileSystem:
        return self._fs

    def open_for(self, authorized: Authorized) -> FileStore | StoreError:
        with self._guard:
            key = ntpath.normcase(authorized.store_dir)
            existing = self._open.get(key)
            if existing is not None:
                return existing
            opened = FileStore.open(
                self._fs, authorized.store_dir, authorized.project_root, self._clock
            )
            if isinstance(opened, StoreError):
                return opened
            try:
                if self._on_first_open is not None:
                    self._on_first_open(opened, authorized.project_root)
                self._remember(KnownStore(authorized.store_dir, authorized.project_root))
            except BaseException:
                opened.close()
                raise
            self._open[key] = opened
            self._roots[key] = authorized.project_root
            return opened

    def open_known(self) -> tuple[str, ...]:
        """Open every listed store that still exists; returns the store folders skipped."""
        skipped: list[str] = []
        with self._guard:
            for known in self._read_known():
                stat = self._fs.stat(known.store_dir)
                if stat is None or not stat.is_dir:
                    skipped.append(known.store_dir)
                    continue
                key = ntpath.normcase(known.store_dir)
                if key in self._open:
                    continue
                opened = FileStore.open(self._fs, known.store_dir, known.project_root, self._clock)
                if isinstance(opened, StoreError):
                    skipped.append(known.store_dir)
                else:
                    self._open[key] = opened
                    self._roots[key] = known.project_root
        return tuple(skipped)

    def store_of_job(self, job_id: str) -> FileStore | None:
        with self._guard:
            return next((s for s in self._open.values() if s.has_job(job_id)), None)

    def store_of_report(self, report_id: str) -> FileStore | None:
        with self._guard:
            return next((s for s in self._open.values() if s.has_report(report_id)), None)

    def stores(self) -> tuple[FileStore, ...]:
        with self._guard:
            return tuple(self._open.values())

    def entries(self) -> tuple[tuple[FileStore, str], ...]:
        """Every open store with its project folder."""
        with self._guard:
            return tuple((store, self._roots[key]) for key, store in self._open.items())

    def close_all(self) -> None:
        with self._guard:
            for store in self._open.values():
                store.close()
            self._open = {}
            self._roots = {}

    def _read_known(self) -> tuple[KnownStore, ...]:
        if self._fs.stat(self._known_path) is None:
            return ()
        return _parse_known(self._fs.read_bytes(self._known_path))

    def _remember(self, store: KnownStore) -> None:
        known = self._read_known()
        key = ntpath.normcase(store.store_dir)
        if any(ntpath.normcase(k.store_dir) == key for k in known):
            return
        self._fs.make_dirs(ntpath.dirname(self._known_path))
        listed: list[JsonValue] = [
            {"store_dir": k.store_dir, "project_root": k.project_root} for k in (*known, store)
        ]
        self._fs.write_atomic(self._known_path, encode({"stores": listed}))


def _parse_known(data: bytes) -> tuple[KnownStore, ...]:
    """Lenient: anything that is not a list of well-formed entries is ignored."""
    document = decode_json(data, "known-stores.json")
    if not isinstance(document, dict):
        return ()
    entries = document.get("stores")
    found: list[KnownStore] = []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            store_dir, root = entry.get("store_dir"), entry.get("project_root")
            if isinstance(store_dir, str) and isinstance(root, str):
                found.append(KnownStore(store_dir, root))
    return tuple(found)
