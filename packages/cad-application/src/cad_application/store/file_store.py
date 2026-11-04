"""FileStore: the project store over the FileSystem port (spec 13.2.1, 13.2.2, 13.2.5)."""

import ntpath
import re
import threading
from dataclasses import replace
from typing import Final, Self

from cad_ir.core.json_types import JsonValue

from cad_application.ports import Clock, FileSystem, Lock, LockHeld
from cad_application.store.codec import (
    Obj,
    decode_json,
    decode_record,
    encode,
    format_ts,
    get_obj,
    get_str,
)
from cad_application.store.errors import StoreError, locked
from cad_application.store.job_files import JobFiles
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import JournalRecord
from cad_application.store.records import DrawingMatch, DrawingRecord, JobWarning, ReportMeta

STORE_VERSION: Final = "0.1"
GITIGNORE: Final = (
    "# Written by sw-mcp (spec 13.2.5). Regenerable, large or local:\n"
    "derived/\nsnapshots/\nreports/\njobs/\nbackups/\nindex.json\n.lock\n*.tmp-*\n"
)
FOLDERS: Final = (
    "modules",
    "parts",
    "drawings",
    "derived",
    "snapshots",
    "reports",
    "jobs",
    "backups",
)
_TMP: Final = re.compile(r"\.tmp-[0-9a-fA-F]+$")
_META_SUFFIX: Final = ".meta.json"


def _same(a: str, b: str) -> bool:
    return ntpath.normcase(a) == ntpath.normcase(b)


class FileStore:
    """One writer per store folder; created with :meth:`open`."""

    def __init__(self, fs: FileSystem, store_dir: str, clock: Clock, lock: Lock) -> None:
        self._fs = fs
        self._dir = store_dir
        self._clock = clock
        self._lock: Lock | None = lock
        self._guard = threading.RLock()
        self._index: dict[str, tuple[str, str]] = {}
        self._jobs = JobFiles(fs, ntpath.join(store_dir, "jobs"))

    @property
    def store_dir(self) -> str:
        return self._dir

    def path(self, *parts: str) -> str:
        return ntpath.join(self._dir, *parts)

    def timestamp(self) -> str:
        return format_ts(self._clock.now())

    # --- open and close ------------------------------------------------------------------

    @classmethod
    def open(
        cls, fs: FileSystem, store_dir: str, project_root: str, clock: Clock
    ) -> "FileStore | StoreError":
        fs.make_dirs(store_dir)
        try:
            lock = fs.lock_exclusive(ntpath.join(store_dir, ".lock"))
        except LockHeld:
            return locked()
        store = cls(fs, store_dir, clock, lock)
        try:
            error = store._initialise(project_root)
        except BaseException:
            lock.release()
            raise
        if error is not None:
            lock.release()
            return error
        return store

    def close(self) -> None:
        with self._guard:
            if self._lock is not None:
                self._lock.release()
                self._lock = None

    def _initialise(self, project_root: str) -> StoreError | None:
        error = self._check_manifest(project_root)
        if error is not None:
            return error
        gitignore = self.path(".gitignore")
        if self._fs.stat(gitignore) is None:
            self._fs.write_atomic(gitignore, GITIGNORE.encode("utf-8"))
        for folder in FOLDERS:
            self._fs.make_dirs(self.path(folder))
        self._remove_tmp(self._dir)
        return self._load_index()

    def _check_manifest(self, project_root: str) -> StoreError | None:
        manifest_path = self.path("store.json")
        if self._fs.stat(manifest_path) is None:
            manifest: JsonValue = {
                "store_version": STORE_VERSION,
                "created_at": self.timestamp(),
                "project_root": project_root,
            }
            self._fs.write_atomic(manifest_path, encode(manifest))
            return None
        loaded = decode_record(self._fs.read_bytes(manifest_path), "StoreManifest", "store.json")
        if isinstance(loaded, StoreError):
            return loaded
        major = get_str(loaded, "store_version").partition(".")[0]
        if major != STORE_VERSION.partition(".")[0]:
            return StoreError(
                "STORE_CORRUPT",
                "The project store was made by a newer version (store_version).",
                {"reason": "store_version"},
            )
        return None

    def _remove_tmp(self, folder: str) -> None:
        for name in self._fs.list_dir(folder):
            path = ntpath.join(folder, name)
            stat = self._fs.stat(path)
            if stat is not None and stat.is_dir:
                self._remove_tmp(path)
            elif _TMP.search(name):
                self._fs.remove(path)

    # --- index ---------------------------------------------------------------------------

    def _drawing_files(self) -> tuple[str, ...]:
        return tuple(n for n in self._fs.list_dir(self.path("drawings")) if n.endswith(".json"))

    def _load_index(self) -> StoreError | None:
        index_path = self.path("index.json")
        stat = self._fs.stat(index_path)
        if stat is not None and not self._index_stale(stat.mtime_ns):
            loaded = decode_record(self._fs.read_bytes(index_path), "Index", "index.json")
            if not isinstance(loaded, StoreError):
                self._index = {
                    key: (get_str(entry, "path"), get_str(entry, "fingerprint"))
                    for key, entry in (
                        (k, _entry(v)) for k, v in get_obj(loaded, "drawings").items()
                    )
                }
                return None
        return self._rebuild_index()

    def _index_stale(self, index_mtime_ns: int) -> bool:
        for name in self._drawing_files():
            stat = self._fs.stat(self.path("drawings", name))
            if stat is not None and stat.mtime_ns > index_mtime_ns:
                return True
        return False

    def _rebuild_index(self) -> StoreError | None:
        rebuilt: dict[str, tuple[str, str]] = {}
        for name in self._drawing_files():
            record = self._read_drawing(name.removesuffix(".json"))
            if isinstance(record, StoreError):
                return record
            if record is not None:
                rebuilt[record.drawing_id] = (record.path, record.fingerprint)
        self._index = rebuilt
        self._write_index()
        return None

    def _write_index(self) -> None:
        drawings: Obj = {k: {"path": p, "fingerprint": f} for k, (p, f) in self._index.items()}
        index: JsonValue = {"built_at": self.timestamp(), "drawings": drawings}
        self._fs.write_atomic(self.path("index.json"), encode(index))

    # --- drawings ------------------------------------------------------------------------

    def _read_drawing(self, drawing_id: str) -> DrawingRecord | StoreError | None:
        file = f"drawings\\{drawing_id}.json"
        path = self.path(file)
        if self._fs.stat(path) is None:
            return None
        loaded = decode_record(self._fs.read_bytes(path), "DrawingRecord", file)
        if isinstance(loaded, StoreError):
            return loaded
        return DrawingRecord.from_json(loaded)

    def get_drawing(self, drawing_id: str) -> DrawingRecord | StoreError | None:
        with self._guard:
            return self._read_drawing(drawing_id)

    def put_drawing(self, record: DrawingRecord) -> None:
        with self._guard:
            self._fs.write_atomic(
                self.path("drawings", f"{record.drawing_id}.json"), encode(record.to_json())
            )
            self._index = {**self._index, record.drawing_id: (record.path, record.fingerprint)}
            self._write_index()

    def match_drawing(self, path: str, fingerprint: str) -> DrawingMatch:
        """The 13.2.1 matching rule; nothing is written."""
        with self._guard:
            now = self.timestamp()
            for drawing_id, (known_path, _) in self._index.items():
                if _same(known_path, path):
                    return self._updated(drawing_id, path, fingerprint, now)
            same_content = [i for i, (_, f) in self._index.items() if f == fingerprint]
            if len(same_content) == 1:
                return self._updated(same_content[0], path, fingerprint, now)
            if len(same_content) > 1:
                warning = JobWarning(
                    "drawing_match_ambiguous",
                    "Several known drawings have this content; a new drawing record was made.",
                )
                return DrawingMatch(None, warning)
            return DrawingMatch(None, None)

    def _updated(self, drawing_id: str, path: str, fingerprint: str, now: str) -> DrawingMatch:
        record = self._read_drawing(drawing_id)
        if not isinstance(record, DrawingRecord):
            return DrawingMatch(None, None)
        return DrawingMatch(
            replace(record, path=path, fingerprint=fingerprint, updated_at=now), None
        )

    def find_drawing(self, path: str, fingerprint: str) -> DrawingRecord | None:
        return self.match_drawing(path, fingerprint).record

    # --- snapshots and reports -----------------------------------------------------------

    def put_snapshot(self, drawing_id: str, snapshot_id: str, doc: JsonValue) -> None:
        with self._guard:
            self._fs.make_dirs(self.path("snapshots", drawing_id))
            self._fs.write_new(
                self.path("snapshots", drawing_id, f"{snapshot_id}.json"), encode(doc)
            )

    def get_snapshot(self, drawing_id: str, snapshot_id: str) -> JsonValue | StoreError | None:
        file = f"snapshots\\{drawing_id}\\{snapshot_id}.json"
        path = self.path(file)
        with self._guard:
            if self._fs.stat(path) is None:
                return None
            return decode_json(self._fs.read_bytes(path), file)

    def put_report(self, report_id: str, report: JsonValue, meta: ReportMeta) -> None:
        with self._guard:
            self._fs.write_new(
                self.path("reports", f"{report_id}{_META_SUFFIX}"), encode(meta.to_json())
            )
            self._fs.write_new(self.path("reports", f"{report_id}.json"), encode(report))

    def get_report(self, report_id: str) -> tuple[JsonValue, ReportMeta] | StoreError | None:
        meta_file = f"reports\\{report_id}{_META_SUFFIX}"
        report_file = f"reports\\{report_id}.json"
        with self._guard:
            if self._fs.stat(self.path(meta_file)) is None:
                return None
            loaded = decode_record(
                self._fs.read_bytes(self.path(meta_file)), "ReportMeta", meta_file
            )
            if isinstance(loaded, StoreError):
                return loaded
            if self._fs.stat(self.path(report_file)) is None:
                return None
            report = decode_json(self._fs.read_bytes(self.path(report_file)), report_file)
            if isinstance(report, StoreError):
                return report
            return report, ReportMeta.from_json(loaded)

    # --- lookups -------------------------------------------------------------------------

    def has_job(self, job_id: str) -> bool:
        stat = self._fs.stat(self.path("jobs", job_id))
        return stat is not None and stat.is_dir

    def has_report(self, report_id: str) -> bool:
        return self._fs.stat(self.path("reports", f"{report_id}{_META_SUFFIX}")) is not None

    # --- jobs and journal ----------------------------------------------------------------

    def create_job(self, record: JobRecord) -> None:
        with self._guard:
            self._jobs.create(record, self.timestamp())

    def append(self, job_id: str, record: JournalRecord) -> None:
        with self._guard:
            self._jobs.append(job_id, record)

    def put_job(self, record: JobRecord) -> None:
        with self._guard:
            self._jobs.put(record)

    def get_job(self, job_id: str) -> JobRecord | StoreError | None:
        with self._guard:
            return self._jobs.get(job_id)

    def list_job_ids(self) -> tuple[str, ...]:
        with self._guard:
            return self._jobs.list_ids()

    def list_jobs(self) -> tuple[JobRecord, ...] | StoreError:
        with self._guard:
            found = [self._jobs.get(job_id) for job_id in self._jobs.list_ids()]
        jobs: list[JobRecord] = []
        for job in found:
            if isinstance(job, StoreError):
                return job
            if job is not None:
                jobs.append(job)
        return tuple(jobs)

    def read_journal(self, job_id: str) -> tuple[JournalRecord, ...] | StoreError:
        with self._guard:
            return self._jobs.read_journal(job_id)

    def delete_job(self, job_id: str) -> None:
        with self._guard:
            self._jobs.delete(job_id)

    # --- listing and deleting, for clean-up ----------------------------------------------

    def list_drawings(self) -> tuple[DrawingRecord, ...] | StoreError:
        with self._guard:
            found = [self._read_drawing(n.removesuffix(".json")) for n in self._drawing_files()]
        records: list[DrawingRecord] = []
        for record in found:
            if isinstance(record, StoreError):
                return record
            if record is not None:
                records.append(record)
        return tuple(records)

    def list_snapshot_ids(self, drawing_id: str) -> tuple[str, ...]:
        with self._guard:
            folder = self.path("snapshots", drawing_id)
            if self._fs.stat(folder) is None:
                return ()
            return tuple(
                n.removesuffix(".json") for n in self._fs.list_dir(folder) if n.endswith(".json")
            )

    def delete_snapshot(self, drawing_id: str, snapshot_id: str) -> None:
        with self._guard:
            self._fs.remove(self.path("snapshots", drawing_id, f"{snapshot_id}.json"))

    def list_report_metas(self) -> tuple[ReportMeta, ...] | StoreError:
        with self._guard:
            names = [n for n in self._fs.list_dir(self.path("reports")) if n.endswith(_META_SUFFIX)]
            found = [self._read_meta(n.removesuffix(_META_SUFFIX)) for n in names]
        metas: list[ReportMeta] = []
        for meta in found:
            if isinstance(meta, StoreError):
                return meta
            metas.append(meta)
        return tuple(metas)

    def delete_report(self, report_id: str) -> None:
        """The report first, then its meta, so a crash leaves a meta that clean-up retries."""
        with self._guard:
            report = self.path("reports", f"{report_id}.json")
            if self._fs.stat(report) is not None:
                self._fs.remove(report)
            self._fs.remove(self.path("reports", f"{report_id}{_META_SUFFIX}"))

    def _read_meta(self, report_id: str) -> ReportMeta | StoreError:
        file = rf"reports\{report_id}{_META_SUFFIX}"
        loaded = decode_record(self._fs.read_bytes(self.path(file)), "ReportMeta", file)
        return loaded if isinstance(loaded, StoreError) else ReportMeta.from_json(loaded)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _entry(value: JsonValue) -> Obj:
    if not isinstance(value, dict):
        raise TypeError("index entry")
    return value
