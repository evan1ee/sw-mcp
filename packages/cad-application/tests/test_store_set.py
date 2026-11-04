"""StoreSet: one open store per folder, the known-stores list, lookup by ID (spec 13.2.1)."""

import json

from cad_application.paths import Authorized
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.records import ReportMeta
from cad_application.store.store_set import StoreSet
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem

LOCAL = "C:\\Users\\me\\AppData\\Local"
KNOWN = f"{LOCAL}\\sw-mcp\\known-stores.json"
IDS = SequentialIdSource()


def _authorized(project: str) -> Authorized:
    return Authorized(
        path=f"{project}\\a.slddrw",
        root=project,
        project_root=project,
        store_dir=f"{project}\\.cad",
        in_vault=False,
    )


def _fs() -> MemoryFileSystem:
    fs = MemoryFileSystem()
    fs.make_dirs("C:\\ProjA")
    fs.make_dirs("C:\\ProjB")
    fs.make_dirs(LOCAL)
    return fs


def test_open_for_opens_once_and_lists_store() -> None:
    fs = _fs()
    stores = StoreSet(fs, FakeClock(), KNOWN)
    first = stores.open_for(_authorized("C:\\ProjA"))
    again = stores.open_for(_authorized("c:\\proja"))
    assert isinstance(first, FileStore)
    assert again is first
    listed = json.loads(fs.read_bytes(KNOWN))["stores"]
    assert listed == [{"store_dir": "C:\\ProjA\\.cad", "project_root": "C:\\ProjA"}]
    stores.close_all()


def test_store_set_finds_job_and_report_by_id() -> None:
    fs = _fs()
    stores = StoreSet(fs, FakeClock(), KNOWN)
    store_a = stores.open_for(_authorized("C:\\ProjA"))
    store_b = stores.open_for(_authorized("C:\\ProjB"))
    assert isinstance(store_a, FileStore)
    assert isinstance(store_b, FileStore)
    job_id = IDS.new_id("job")
    rep_id = IDS.new_id("rep")
    fs.make_dirs(f"C:\\ProjB\\.cad\\jobs\\{job_id}")
    meta = ReportMeta(rep_id, IDS.new_id("job"), "drw_x", "snap_x", "2026-11-04T09:00:00.000Z", ())
    store_a.put_report(rep_id, {"verdict": "pass"}, meta)
    assert stores.store_of_job(job_id) is store_b
    assert stores.store_of_report(rep_id) is store_a
    assert stores.store_of_job(IDS.new_id("job")) is None
    assert stores.store_of_report(IDS.new_id("rep")) is None
    stores.close_all()


def test_known_store_locked_elsewhere_is_skipped() -> None:
    fs = _fs()
    setup = StoreSet(fs, FakeClock(), KNOWN)
    assert isinstance(setup.open_for(_authorized("C:\\ProjB")), FileStore)
    setup.close_all()
    other = StoreSet(fs, FakeClock(), KNOWN)
    assert isinstance(other.open_for(_authorized("C:\\ProjA")), FileStore)  # listed, held by other
    mine = StoreSet(fs, FakeClock(), KNOWN)
    skipped = mine.open_known()
    assert skipped == ("C:\\ProjA\\.cad",)
    assert mine.store_of_job(IDS.new_id("job")) is None
    job_id = IDS.new_id("job")
    fs.make_dirs(f"C:\\ProjB\\.cad\\jobs\\{job_id}")
    assert mine.store_of_job(job_id) is not None  # ProjB was opened by open_known
    mine.close_all()
    other.close_all()


def test_open_known_with_no_list_opens_nothing() -> None:
    stores = StoreSet(_fs(), FakeClock(), KNOWN)
    assert stores.open_known() == ()


def test_open_for_reports_store_errors() -> None:
    fs = _fs()
    stores = StoreSet(fs, FakeClock(), KNOWN)
    held = FileStore.open(fs, "C:\\ProjA\\.cad", "C:\\ProjA", FakeClock())
    assert isinstance(held, FileStore)
    result = stores.open_for(_authorized("C:\\ProjA"))
    assert isinstance(result, StoreError)
    assert result.code == "STORE_LOCKED"
    held.close()
