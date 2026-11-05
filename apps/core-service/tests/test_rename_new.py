"""Tests for FileSystem.rename_new (spec 13.2.2)."""

from pathlib import Path

import pytest
from cad_application.testing.memory_fs import MemoryFileSystem
from core_service.os_fs import OsFileSystem


def test_rename_new_refuses_existing_memory_fs() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs("C:\\Work")
    fs.write_atomic("C:\\Work\\src.txt", b"source")
    fs.write_atomic("C:\\Work\\tgt.txt", b"target")

    # Target exists -> raises FileExistsError
    with pytest.raises(FileExistsError):
        fs.rename_new("C:\\Work\\src.txt", "C:\\Work\\tgt.txt")

    assert fs.read_bytes("C:\\Work\\src.txt") == b"source"
    assert fs.read_bytes("C:\\Work\\tgt.txt") == b"target"

    # Target does not exist -> succeeds
    fs.rename_new("C:\\Work\\src.txt", "C:\\Work\\new.txt")
    assert fs.stat("C:\\Work\\src.txt") is None
    assert fs.read_bytes("C:\\Work\\new.txt") == b"source"


def test_rename_new_refuses_existing_os_fs(tmp_path: Path) -> None:
    fs = OsFileSystem()
    src = str(tmp_path / "src.txt")
    tgt = str(tmp_path / "tgt.txt")
    new_tgt = str(tmp_path / "new.txt")

    fs.write_atomic(src, b"source")
    fs.write_atomic(tgt, b"target")

    # Target exists -> raises FileExistsError
    with pytest.raises(FileExistsError):
        fs.rename_new(src, tgt)

    assert fs.read_bytes(src) == b"source"
    assert fs.read_bytes(tgt) == b"target"

    # Target does not exist -> succeeds
    fs.rename_new(src, new_tgt)
    assert fs.stat(src) is None
    assert fs.read_bytes(new_tgt) == b"source"
