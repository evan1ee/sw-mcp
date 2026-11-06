"""A JobEngine wired to in-memory doubles, for engine and job tests."""

import threading
from collections.abc import Mapping
from dataclasses import dataclass

from cad_drawing.checks import TitleBlockMapping
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult

from cad_application.config.settings import Settings
from cad_application.jobs.engine import JobEngine
from cad_application.jobs.model import CheckDrawingSpec, JobView
from cad_application.paths import Authorized
from cad_application.ports import BackendUnavailable, Clock
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import JournalRecord
from cad_application.store.records import DrawingRecord, ReportMeta
from cad_application.store.store_set import StoreSet
from cad_application.testing.builders import PROJECT_ROOT, STORE_DIR
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import (
    FakeBackend,
    FakeBackendProvider,
    ListEventLog,
    SequentialIdSource,
    make_hello,
)
from cad_application.testing.memory_fs import MemoryFileSystem

DRAWING = "C:\\Work\\a.slddrw"
FINGERPRINT = "sha256:" + "a" * 64
KNOWN_STORES = "C:\\Users\\u\\AppData\\Local\\sw-mcp\\known-stores.json"


@dataclass
class Rig:
    fs: MemoryFileSystem
    clock: Clock
    ids: SequentialIdSource
    log: ListEventLog
    stores: StoreSet
    provider: FakeBackendProvider
    backend: FakeBackend
    engine: JobEngine

    @staticmethod
    def spec(sheets: tuple[str, ...] | None = None, path: str = DRAWING) -> CheckDrawingSpec:
        authorized = Authorized(path, PROJECT_ROOT, PROJECT_ROOT, STORE_DIR, False)
        return CheckDrawingSpec(authorized, FINGERPRINT, sheets)

    def submit(self, sheets: tuple[str, ...] | None = None) -> JobView:
        view = self.engine.submit(self.spec(sheets), self.ids.new_id("req"))
        if not isinstance(view, JobView):
            raise AssertionError(view)
        return view

    def store(self) -> FileStore:
        opened = self.stores.open_for(self.spec().authorized)
        if not isinstance(opened, FileStore):
            raise AssertionError(opened)
        return opened

    def journal(self, job_id: str) -> tuple[JournalRecord, ...]:
        journal = self.store().read_journal(job_id)
        if isinstance(journal, StoreError):
            raise AssertionError(journal)
        return journal

    def report(self, report_id: str) -> tuple[dict[str, JsonValue], ReportMeta]:
        stored = self.store().get_report(report_id)
        if stored is None or isinstance(stored, StoreError) or not isinstance(stored[0], dict):
            raise AssertionError(stored)
        return stored[0], stored[1]

    def drawings(self) -> tuple[DrawingRecord, ...]:
        found = self.store().list_drawings()
        if isinstance(found, StoreError):
            raise AssertionError(found)
        return found

    def job(self, job_id: str) -> JobRecord:
        record = self.store().get_job(job_id)
        if not isinstance(record, JobRecord):
            raise AssertionError(record)
        return record


def make_rig(  # noqa: PLR0913 - a builder with one knob per double
    *,
    snapshot: JsonValue = None,
    open_owned: bool = True,
    hello: HelloResult | None = None,
    clock: Clock | None = None,
    fs: MemoryFileSystem | None = None,
    unavailable: BackendUnavailable | None = None,
    mappings: Mapping[str, TitleBlockMapping] | None = None,
    backend: FakeBackend | None = None,
    block: threading.Event | None = None,
) -> Rig:
    fs = fs or MemoryFileSystem()
    clock = clock or FakeClock()
    ids, log = SequentialIdSource(), ListEventLog()
    fs.make_dirs(PROJECT_ROOT)
    backend = backend or FakeBackend(
        hello or make_hello(), snapshot=snapshot, open_owned=open_owned, block=block
    )
    provider = FakeBackendProvider(backend, unavailable)
    stores = StoreSet(fs, clock, KNOWN_STORES)
    known = dict(mappings or {})
    engine = JobEngine(
        stores, provider, clock, ids, log, lambda _root: Settings(), lambda _s: known
    )
    return Rig(fs, clock, ids, log, stores, provider, backend, engine)
