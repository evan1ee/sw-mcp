"""OsFileSystem: the real adapter behind the FileSystem port (G2). Tests may touch the disk."""

import os
import subprocess
from pathlib import Path

import pytest
from cad_application.ports import LockHeld
from cad_application.store.errors import StoreError
from cad_application.store.file_store import FileStore
from cad_application.testing.fake_clock import FakeClock
from core_service.os_fs import OsFileSystem


def test_os_lock_is_exclusive(tmp_path: Path) -> None:
    first, second = OsFileSystem(), OsFileSystem()
    target = str(tmp_path / ".lock")
    held = first.lock_exclusive(target)
    with pytest.raises(LockHeld):
        second.lock_exclusive(target)
    held.release()
    second.lock_exclusive(target).release()


def test_os_lock_release_is_idempotent(tmp_path: Path) -> None:
    fs = OsFileSystem()
    held = fs.lock_exclusive(str(tmp_path / ".lock"))
    held.release()
    held.release()


def test_os_atomic_write_replaces(tmp_path: Path) -> None:
    fs = OsFileSystem()
    target = tmp_path / "a.json"
    fs.write_atomic(str(target), b"old")
    fs.write_atomic(str(target), b"new")
    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]


def test_os_atomic_write_failure_leaves_no_temporary_file(tmp_path: Path) -> None:
    fs = OsFileSystem()
    (tmp_path / "dir").mkdir()
    with pytest.raises(OSError):  # noqa: PT011 - any OS error will do: the target is a folder
        fs.write_atomic(str(tmp_path / "dir"), b"x")
    assert [p.name for p in tmp_path.iterdir()] == ["dir"]


def test_os_write_new_refuses_existing(tmp_path: Path) -> None:
    fs = OsFileSystem()
    target = str(tmp_path / "snap.json")
    fs.write_new(target, b"first")
    with pytest.raises(FileExistsError):
        fs.write_new(target, b"second")
    assert Path(target).read_bytes() == b"first"
    assert [p.name for p in tmp_path.iterdir()] == ["snap.json"]


def test_os_append_line_adds_newline_terminated_lines(tmp_path: Path) -> None:
    fs = OsFileSystem()
    target = str(tmp_path / "journal.jsonl")
    fs.append_line(target, '{"a":1}')
    fs.append_line(target, '{"b":"ü图"}')
    assert Path(target).read_bytes() == '{"a":1}\n{"b":"ü图"}\n'.encode()


def test_os_stat_missing_is_none_and_reports_kind(tmp_path: Path) -> None:
    fs = OsFileSystem()
    (tmp_path / "f.bin").write_bytes(b"abc")
    found = fs.stat(str(tmp_path / "f.bin"))
    assert found is not None
    assert (found.is_dir, found.size) == (False, 3)
    folder = fs.stat(str(tmp_path))
    assert folder is not None
    assert folder.is_dir
    assert fs.stat(str(tmp_path / "missing")) is None
    assert fs.stat(str(tmp_path / "f.bin" / "below")) is None  # a file is not a folder


def test_os_list_dir_is_sorted(tmp_path: Path) -> None:
    fs = OsFileSystem()
    for name in ("b", "a", "C"):
        (tmp_path / name).write_bytes(b"")
    assert fs.list_dir(str(tmp_path)) == tuple(sorted(os.listdir(tmp_path)))


def test_os_make_dirs_and_remove(tmp_path: Path) -> None:
    fs = OsFileSystem()
    deep = tmp_path / "x" / "y"
    fs.make_dirs(str(deep))
    fs.make_dirs(str(deep))  # already there
    (deep / "f").write_bytes(b"1")
    fs.remove(str(deep / "f"))
    fs.remove(str(deep))
    assert not deep.exists()
    with pytest.raises(FileNotFoundError):
        fs.remove(str(deep))


def test_os_read_bytes(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"\x00\xffbinary")
    assert OsFileSystem().read_bytes(str(tmp_path / "f")) == b"\x00\xffbinary"


def test_os_resolve_follows_junction(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    (target / "a.slddrw").write_bytes(b"x")
    link = tmp_path / "link"
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip("cannot create a junction here")
    resolved = OsFileSystem().resolve(str(link / "a.slddrw"))
    assert os.path.normcase(resolved) == os.path.normcase(str(target / "a.slddrw"))
    assert not resolved.startswith("\\\\?\\")


def test_os_resolve_missing_parent_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        OsFileSystem().resolve(str(tmp_path / "nope" / "a.slddrw"))


def test_file_store_over_os_fs_locks_and_reopens(tmp_path: Path) -> None:
    clock = FakeClock()
    store_dir = str(tmp_path / ".cad")
    first = FileStore.open(OsFileSystem(), store_dir, str(tmp_path), clock)
    assert isinstance(first, FileStore)
    second = FileStore.open(OsFileSystem(), store_dir, str(tmp_path), clock)
    assert isinstance(second, StoreError)
    assert second.code == "STORE_LOCKED"
    first.close()
    third = FileStore.open(OsFileSystem(), store_dir, str(tmp_path), clock)
    assert isinstance(third, FileStore)
    third.close()


def _boom(*_args: object) -> None:
    raise OSError("simulated fault")


@pytest.mark.parametrize("step", ["fsync", "replace"])
def test_os_atomic_write_keeps_the_old_file_when_a_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    fs = OsFileSystem()
    target = tmp_path / "state.json"
    fs.write_atomic(str(target), b"old contents")
    monkeypatch.setattr(os, step, _boom)
    with pytest.raises(OSError, match="simulated fault"):
        fs.write_atomic(str(target), b"new contents that are longer")
    monkeypatch.undo()
    assert target.read_bytes() == b"old contents"
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_os_write_new_leaves_nothing_when_fsync_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fs = OsFileSystem()
    monkeypatch.setattr(os, "fsync", _boom)
    with pytest.raises(OSError, match="simulated fault"):
        fs.write_new(str(tmp_path / "snap.json"), b"x")
    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == []
