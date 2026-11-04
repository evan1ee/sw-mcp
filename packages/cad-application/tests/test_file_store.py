"""FileStore over MemoryFileSystem (spec 13.2.1, 13.2.2, 13.2.5)."""

import json
from collections.abc import Sequence

import pytest
from cad_application.ports import Store
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.store.records import DrawingRecord, JobWarning, ReportMeta
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import SequentialIdSource
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_ir.core.json_types import JsonValue

ROOT = "C:\\Work"
STORE_DIR = "C:\\Work\\.cad"
FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64
FP_C = "sha256:" + "c" * 64
TS = "2026-11-04T09:00:00.000Z"
GITIGNORE = (
    "# Written by sw-mcp (spec 13.2.5). Regenerable, large or local:\n"
    "derived/\nsnapshots/\nreports/\njobs/\nbackups/\nindex.json\n.lock\n*.tmp-*\n"
)
IDS = SequentialIdSource()


def _store(fs: MemoryFileSystem | None = None) -> tuple[FileStore, MemoryFileSystem]:
    fs = fs or MemoryFileSystem()
    fs.make_dirs(ROOT)
    opened = FileStore.open(fs, STORE_DIR, ROOT, FakeClock())
    assert isinstance(opened, FileStore), opened
    return opened, fs


def _drawing(path: str, fingerprint: str = FP_A) -> DrawingRecord:
    return DrawingRecord(
        drawing_id=IDS.new_id("drw"),
        path=path,
        fingerprint=fingerprint,
        produced=False,
        drawing_intent=None,
        latest_snapshot_id=None,
        latest_report_id=None,
        updated_at=TS,
    )


def _meta(report_id: str, drawing_id: str, snapshot_id: str) -> ReportMeta:
    return ReportMeta(
        report_id=report_id,
        execution_id=IDS.new_id("job"),
        drawing_id=drawing_id,
        snapshot_id=snapshot_id,
        created_at=TS,
        job_warnings=(JobWarning("solidworks_version_warning", "newer service pack"),),
    )


def _text(fs: MemoryFileSystem, path: str) -> str:
    return fs.read_bytes(path).decode("utf-8")


def _encode(record: DrawingRecord) -> bytes:
    return json.dumps(record.to_json()).encode()


def test_first_open_creates_layout_and_gitignore() -> None:
    store, fs = _store()
    store.close()
    for folder in ("modules", "parts", "drawings", "derived", "snapshots", "reports", "jobs"):
        stat = fs.stat(f"{STORE_DIR}\\{folder}")
        assert stat is not None
        assert stat.is_dir
    assert _text(fs, f"{STORE_DIR}\\.gitignore") == GITIGNORE
    manifest = json.loads(_text(fs, f"{STORE_DIR}\\store.json"))
    assert manifest["store_version"] == "0.1"
    assert manifest["project_root"] == ROOT
    assert fs.stat(f"{STORE_DIR}\\index.json") is not None


def test_gitignore_never_overwritten() -> None:
    store, fs = _store()
    store.close()
    fs.write_atomic(f"{STORE_DIR}\\.gitignore", b"mine\n")
    reopened, _ = _store(fs)
    reopened.close()
    assert _text(fs, f"{STORE_DIR}\\.gitignore") == "mine\n"


def test_second_open_is_store_locked() -> None:
    first, fs = _store()
    second = FileStore.open(fs, STORE_DIR, ROOT, FakeClock())
    assert isinstance(second, StoreError)
    assert second.code == "STORE_LOCKED"
    first.close()
    third = FileStore.open(fs, STORE_DIR, ROOT, FakeClock())
    assert isinstance(third, FileStore)
    third.close()


def test_unknown_store_major_is_corrupt() -> None:
    store, fs = _store()
    store.close()
    manifest: dict[str, JsonValue] = {
        "store_version": "1.0",
        "created_at": TS,
        "project_root": ROOT,
    }
    fs.write_atomic(f"{STORE_DIR}\\store.json", json.dumps(manifest).encode())
    result = FileStore.open(fs, STORE_DIR, ROOT, FakeClock())
    assert isinstance(result, StoreError)
    assert result.code == "STORE_CORRUPT"
    assert result.details == {"reason": "store_version"}
    again = FileStore.open(fs, STORE_DIR, ROOT, FakeClock())
    assert isinstance(again, StoreError)
    assert again.code == "STORE_CORRUPT"  # the failed open released the lock


def test_tmp_files_removed_at_open() -> None:
    store, fs = _store()
    store.close()
    fs.make_dirs(f"{STORE_DIR}\\snapshots\\drw_x")
    leftovers = (
        f"{STORE_DIR}\\store.json.tmp-0000abcd",
        f"{STORE_DIR}\\snapshots\\drw_x\\snap.json.tmp-00000002",
        f"{STORE_DIR}\\reports\\r.json.tmp-ffffffff",
    )
    for leftover in leftovers:
        fs.write_atomic(leftover, b"torn")
    reopened, _ = _store(fs)
    reopened.close()
    assert all(fs.stat(leftover) is None for leftover in leftovers)
    assert fs.stat(f"{STORE_DIR}\\store.json") is not None


@pytest.mark.parametrize("damage", ["missing", "garbage", "stale"])
def test_index_rebuilt_when_stale(damage: str) -> None:
    store, fs = _store()
    first = _drawing("C:\\Work\\a.slddrw")
    store.put_drawing(first)
    store.close()
    second = _drawing("C:\\Work\\b.slddrw", FP_B)
    index = f"{STORE_DIR}\\index.json"
    if damage == "missing":
        fs.remove(index)
    elif damage == "garbage":
        fs.write_atomic(index, b"{not json")
    # In every case a drawing record exists that the index does not list; for "stale" it is
    # simply newer than the index.
    fs.write_atomic(f"{STORE_DIR}\\drawings\\{second.drawing_id}.json", _encode(second))
    reopened, _ = _store(fs)
    ids = json.loads(_text(fs, index))["drawings"]
    assert set(ids) == {first.drawing_id, second.drawing_id}
    found = reopened.match_drawing("C:\\Work\\b.slddrw", FP_B).record
    assert found is not None
    assert found.drawing_id == second.drawing_id
    reopened.close()


def test_fresh_index_is_not_rebuilt() -> None:
    store, fs = _store()
    store.put_drawing(_drawing("C:\\Work\\a.slddrw"))
    store.close()
    index = f"{STORE_DIR}\\index.json"
    before = fs.stat(index)
    reopened, _ = _store(fs)
    reopened.close()
    assert fs.stat(index) == before


def test_match_drawing_by_path_then_fingerprint() -> None:
    store, _ = _store()
    record = _drawing("C:\\Work\\a.slddrw")
    store.put_drawing(record)
    by_path = store.match_drawing("c:\\work\\A.SLDDRW", FP_B)  # same path, content changed
    assert by_path.warning is None
    assert by_path.record is not None
    assert by_path.record.drawing_id == record.drawing_id
    assert by_path.record.fingerprint == FP_B
    moved = store.match_drawing("C:\\Work\\moved.slddrw", FP_A)  # same content, new path
    assert moved.record is not None
    assert moved.record.drawing_id == record.drawing_id
    assert moved.record.path == "C:\\Work\\moved.slddrw"
    unknown = store.match_drawing("C:\\Work\\new.slddrw", FP_C)
    assert unknown.record is None
    assert unknown.warning is None
    assert store.find_drawing("C:\\Work\\new.slddrw", FP_C) is None
    found = store.find_drawing("C:\\Work\\a.slddrw", FP_A)
    assert found is not None
    assert found.drawing_id == record.drawing_id
    store.close()


def test_ambiguous_fingerprint_makes_new_record_and_warning() -> None:
    store, _ = _store()
    store.put_drawing(_drawing("C:\\Work\\a.slddrw", FP_A))
    store.put_drawing(_drawing("C:\\Work\\b.slddrw", FP_A))
    result = store.match_drawing("C:\\Work\\c.slddrw", FP_A)
    assert result.record is None
    assert result.warning is not None
    assert result.warning.code == "drawing_match_ambiguous"
    store.close()


def test_write_new_refuses_existing() -> None:
    store, fs = _store()
    drawing = _drawing("C:\\Work\\a.slddrw")
    snap_id = IDS.new_id("snap")
    rep_id = IDS.new_id("rep")
    store.put_snapshot(drawing.drawing_id, snap_id, {"v": 1})
    with pytest.raises(FileExistsError):
        store.put_snapshot(drawing.drawing_id, snap_id, {"v": 2})
    assert store.get_snapshot(drawing.drawing_id, snap_id) == {"v": 1}
    meta = _meta(rep_id, drawing.drawing_id, snap_id)
    store.put_report(rep_id, {"verdict": "pass"}, meta)
    with pytest.raises(FileExistsError):
        store.put_report(rep_id, {"verdict": "fail"}, meta)
    stored = store.get_report(rep_id)
    assert isinstance(stored, tuple)
    assert stored[0] == {"verdict": "pass"}
    assert stored[1] == meta
    store.close()
    assert fs.stat(f"{STORE_DIR}\\reports\\{rep_id}.json") is not None


class _SpyFs(MemoryFileSystem):
    def __init__(self) -> None:
        super().__init__()
        self.new_files: list[str] = []

    def write_new(self, path: str, data: bytes) -> None:
        self.new_files.append(path)
        super().write_new(path, data)


def test_put_report_writes_meta_first() -> None:
    fs = _SpyFs()
    store, _ = _store(fs)
    rep_id = IDS.new_id("rep")
    store.put_report(rep_id, {"verdict": "pass"}, _meta(rep_id, IDS.new_id("drw"), "snap_x"))
    names: Sequence[str] = [p.rsplit("\\", 1)[1] for p in fs.new_files]
    assert names == [f"{rep_id}.meta.json", f"{rep_id}.json"]
    store.close()


def test_report_without_meta_is_not_found() -> None:
    store, fs = _store()
    rep_id = IDS.new_id("rep")
    fs.write_atomic(f"{STORE_DIR}\\reports\\{rep_id}.json", b"{}")
    assert store.get_report(rep_id) is None
    assert store.get_report(IDS.new_id("rep")) is None
    store.close()


def test_invalid_record_is_store_corrupt() -> None:
    store, fs = _store()
    record = _drawing("C:\\Work\\a.slddrw")
    store.put_drawing(record)
    path = f"{STORE_DIR}\\drawings\\{record.drawing_id}.json"
    fs.write_atomic(path, b'{"drawing_id": 5}')
    broken = store.get_drawing(record.drawing_id)
    assert isinstance(broken, StoreError)
    assert broken.code == "STORE_CORRUPT"
    fs.write_atomic(path, b"not json at all")
    unreadable = store.get_drawing(record.drawing_id)
    assert isinstance(unreadable, StoreError)
    assert unreadable.code == "STORE_CORRUPT"
    assert "not json" not in unreadable.message  # no file contents in errors
    snap_id = IDS.new_id("snap")
    fs.make_dirs(f"{STORE_DIR}\\snapshots\\{record.drawing_id}")
    fs.write_atomic(f"{STORE_DIR}\\snapshots\\{record.drawing_id}\\{snap_id}.json", b"[")
    bad_snapshot = store.get_snapshot(record.drawing_id, snap_id)
    assert isinstance(bad_snapshot, StoreError)
    rep_id = IDS.new_id("rep")
    fs.write_atomic(f"{STORE_DIR}\\reports\\{rep_id}.meta.json", b'{"report_id": "x"}')
    bad_meta = store.get_report(rep_id)
    assert isinstance(bad_meta, StoreError)
    store.close()


def test_filestore_satisfies_store_port() -> None:
    store, _ = _store()
    port: Store = store
    assert port.get_snapshot("drw_none", "snap_none") is None
    port.close()
