"""MemoryFileSystem: Windows semantics and crash simulation (guideline G2)."""

import ntpath

import pytest
from cad_application.ports import FileSystem, LockHeld
from cad_application.testing.memory_fs import FaultPoint, MemoryFileSystem, SimulatedCrash

DIR = "C:\\Work\\Sub"
TARGET = DIR + "\\data.json"


def _fs(*, fail_at: FaultPoint | None = None) -> MemoryFileSystem:
    fs = MemoryFileSystem(fail_at=fail_at)
    fs.make_dirs(DIR)
    return fs


def test_memory_fs_is_a_file_system() -> None:
    fs: FileSystem = MemoryFileSystem()
    assert fs.stat("C:\\nothing") is None


def test_memory_fs_case_insensitive() -> None:
    fs = _fs()
    fs.write_atomic("C:\\Work\\Sub\\File.TXT", b"x")
    assert fs.read_bytes("c:\\WORK\\sub\\file.txt") == b"x"
    assert fs.list_dir("C:\\work\\SUB") == ("File.TXT",)
    assert fs.resolve("c:\\work\\sub\\file.txt") == "C:\\Work\\Sub\\File.TXT"
    stat = fs.stat("C:\\WORK")
    assert stat is not None
    assert stat.is_dir


def test_memory_fs_accepts_forward_slashes_and_dots() -> None:
    fs = _fs()
    fs.write_atomic("C:/Work/Sub/../Sub/a.txt", b"x")
    assert fs.read_bytes(DIR + "\\a.txt") == b"x"


def test_memory_fs_junction_resolves() -> None:
    fs = MemoryFileSystem(junctions={"C:\\Root\\Link": "D:\\Elsewhere"})
    fs.make_dirs("D:\\Elsewhere")
    fs.write_atomic("D:\\Elsewhere\\f.txt", b"payload")
    assert fs.resolve("c:\\root\\link\\f.txt") == "D:\\Elsewhere\\f.txt"
    assert fs.read_bytes("C:\\Root\\Link\\f.txt") == b"payload"
    assert fs.list_dir("C:\\Root\\Link") == ("f.txt",)


def test_resolve_of_missing_leaf_is_normalised_but_missing_parent_raises() -> None:
    fs = _fs()
    assert fs.resolve(DIR + "\\..\\Sub\\new.txt") == DIR + "\\new.txt"
    with pytest.raises(FileNotFoundError):
        fs.resolve("C:\\Work\\Missing\\new.txt")


def test_stat_reports_kind_size_and_a_growing_mtime() -> None:
    fs = _fs()
    fs.write_atomic(TARGET, b"abc")
    first = fs.stat(TARGET)
    assert first is not None
    assert (first.is_dir, first.size) == (False, 3)
    fs.write_atomic(TARGET, b"abcdef")
    expected_size = len(b"abcdef")
    second = fs.stat(TARGET)
    assert second is not None
    assert second.size == expected_size
    assert second.mtime_ns > first.mtime_ns
    assert fs.stat(DIR + "\\missing") is None


def test_read_missing_and_directory_raise() -> None:
    fs = _fs()
    with pytest.raises(FileNotFoundError):
        fs.read_bytes(TARGET)
    with pytest.raises(IsADirectoryError):
        fs.read_bytes(DIR)


def test_write_atomic_needs_a_parent() -> None:
    with pytest.raises(FileNotFoundError):
        MemoryFileSystem().write_atomic("C:\\nowhere\\a.json", b"x")


def test_remove_deletes_a_file_and_an_empty_folder() -> None:
    fs = _fs()
    fs.write_atomic(TARGET, b"x")
    fs.remove(TARGET)
    assert fs.stat(TARGET) is None
    fs.remove(DIR)
    assert fs.stat(DIR) is None
    with pytest.raises(FileNotFoundError):
        fs.remove(TARGET)


def test_write_new_refuses_existing() -> None:
    fs = _fs()
    fs.write_new(TARGET, b"first")
    with pytest.raises(FileExistsError):
        fs.write_new(TARGET.upper(), b"second")
    assert fs.read_bytes(TARGET) == b"first"
    assert [n for n in fs.list_dir(DIR) if ".tmp-" in n] == []


@pytest.mark.parametrize("existing", [True, False], ids=["replace", "create"])
@pytest.mark.parametrize("kind", ["write", "fsync", "rename"])
def test_atomic_write_survives_crash_at_every_step(kind: str, existing: bool) -> None:
    point: FaultPoint = (kind, 2 if existing else 1)  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]
    fs = _fs(fail_at=point)
    if existing:
        fs.write_atomic(TARGET, b"old")
    with pytest.raises(SimulatedCrash):
        fs.write_atomic(TARGET, b"new")
    stat = fs.stat(TARGET)
    if stat is None:
        assert not existing
    else:
        assert fs.read_bytes(TARGET) in (b"old", b"new")
    assert [n for n in fs.list_dir(DIR) if n != "data.json"] == [
        n for n in fs.list_dir(DIR) if ".tmp-" in n
    ]


@pytest.mark.parametrize("kind", ["write", "fsync", "rename"])
def test_write_new_crash_never_leaves_a_partial_target(kind: str) -> None:
    point: FaultPoint = (kind, 1)  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]
    fs = _fs(fail_at=point)
    with pytest.raises(SimulatedCrash):
        fs.write_new(TARGET, b"complete")
    if fs.stat(TARGET) is not None:
        assert fs.read_bytes(TARGET) == b"complete"


def test_fault_fires_once() -> None:
    fs = _fs(fail_at=("rename", 1))
    with pytest.raises(SimulatedCrash):
        fs.write_atomic(TARGET, b"a")
    fs.write_atomic(TARGET, b"b")
    assert fs.read_bytes(TARGET) == b"b"


def test_append_line_appends_whole_lines() -> None:
    fs = _fs()
    fs.append_line(TARGET, '{"a": 1}')
    fs.append_line(TARGET, '{"a": 2}')
    assert fs.read_bytes(TARGET) == b'{"a": 1}\n{"a": 2}\n'


def test_append_line_crash_leaves_torn_line() -> None:
    fs = _fs(fail_at=("write", 2))
    fs.append_line(TARGET, "first record")
    with pytest.raises(SimulatedCrash):
        fs.append_line(TARGET, "second record")
    data = fs.read_bytes(TARGET)
    assert data.startswith(b"first record\n")
    torn = data.removeprefix(b"first record\n")
    assert torn
    assert not data.endswith(b"\n")
    assert b"second record".startswith(torn)
    assert torn != b"second record"


def test_lock_is_exclusive_until_released() -> None:
    fs = _fs()
    lock_path = DIR + "\\.lock"
    lock = fs.lock_exclusive(lock_path)
    with pytest.raises(LockHeld):
        fs.lock_exclusive(lock_path.upper())
    lock.release()
    again = fs.lock_exclusive(lock_path)
    again.release()
    again.release()  # releasing twice is harmless
    assert fs.read_bytes(lock_path) == b""


def test_a_crash_can_drop_every_lock() -> None:
    fs = _fs()
    fs.lock_exclusive(DIR + "\\.lock")
    fs.drop_locks()
    fs.lock_exclusive(DIR + "\\.lock").release()


def test_names_keep_their_case_and_list_sorted() -> None:
    fs = _fs()
    for name in ("b.txt", "A.txt", "c.txt"):
        fs.write_atomic(ntpath.join(DIR, name), b"")
    assert fs.list_dir(DIR) == ("A.txt", "b.txt", "c.txt")
