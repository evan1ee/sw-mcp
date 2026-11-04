"""The check_drawing handler (spec 12.4.5): validate, authorize, fingerprint, queue."""

import hashlib

import pytest
from cad_application.config.settings import ConfigError
from cad_application.store.file_store import FileStore
from cad_application.testing.builders import PROJECT_ROOT, STORE_DIR
from cad_application.testing.job_rig import DRAWING
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_application.testing.tool_rig import ToolRig, make_tool_rig
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]

CATALOGUED = {
    "IR_SCHEMA_INVALID",
    "AUTH_PATH_DENIED",
    "FILE_NOT_FOUND",
    "CONFIG_INVALID",
    "STORE_LOCKED",
    "STORE_CORRUPT",
}
JOB_ONE = "job_00000000000000000000000001"
JOB_TWO = "job_00000000000000000000000002"
CONTENT = b"drawing bytes"


def _ready() -> ToolRig:
    rig = make_tool_rig()
    rig.write_drawing(DRAWING, CONTENT)
    return rig


def test_check_drawing_returns_execution_id_and_position() -> None:
    rig = _ready()
    first = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.data_of(first) == {"execution_id": JOB_ONE, "queued_position": 0}
    second = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.data_of(second) == {"execution_id": JOB_TWO, "queued_position": 1}
    assert first.summary == f"drawing check queued: {JOB_ONE} (position 0)"


def test_check_drawing_creates_a_planned_job_with_the_fingerprint() -> None:
    rig = _ready()
    rig.call("check_drawing", {"path": DRAWING, "sheets": ["Sheet1", "Sheet2"]})
    record = rig.rig.job(JOB_ONE)
    assert record.state == "PLANNED"
    assert record.fingerprint == "sha256:" + hashlib.sha256(CONTENT).hexdigest()
    assert record.arguments == {"path": DRAWING, "sheets": ["Sheet1", "Sheet2"]}
    assert record.project_root == PROJECT_ROOT


def test_check_drawing_path_denied_creates_no_job() -> None:
    rig = _ready()
    result = rig.call("check_drawing", {"path": "D:\\Other\\a.slddrw"})
    assert ToolRig.code_of(result) == "AUTH_PATH_DENIED"
    assert rig.rig.store().list_job_ids() == ()
    assert not rig.rig.engine.run_next()


def test_check_drawing_missing_file() -> None:
    rig = _ready()
    result = rig.call("check_drawing", {"path": "C:\\Work\\missing.slddrw"})
    assert ToolRig.code_of(result) == "FILE_NOT_FOUND"
    assert rig.rig.store().list_job_ids() == ()


def test_check_drawing_not_slddrw() -> None:
    rig = _ready()
    rig.write_drawing("C:\\Work\\a.sldprt")
    result = rig.call("check_drawing", {"path": "C:\\Work\\a.sldprt"})
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"
    assert rig.rig.store().list_job_ids() == ()


def test_check_drawing_suffix_is_case_insensitive() -> None:
    rig = make_tool_rig()
    rig.write_drawing("C:\\Work\\B.SLDDRW")
    result = rig.call("check_drawing", {"path": "C:\\Work\\B.SLDDRW"})
    assert ToolRig.code_of(result) is None


def test_check_drawing_invalid_project_config_creates_no_job() -> None:
    error = ConfigError("C:\\Work\\.cad\\config.toml", "drawing.check.epsilon_mm", None, "bad")
    rig = make_tool_rig(project_settings=lambda _root: error)
    rig.write_drawing(DRAWING)
    result = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.code_of(result) == "CONFIG_INVALID"
    assert not rig.rig.engine.run_next()


def test_check_drawing_store_locked() -> None:
    rig = _ready()
    holder = FileStore.open(rig.rig.fs, STORE_DIR, PROJECT_ROOT, rig.rig.clock)
    assert isinstance(holder, FileStore)
    result = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.code_of(result) == "STORE_LOCKED"
    holder.close()


def test_check_drawing_store_corrupt() -> None:
    rig = _ready()
    rig.rig.fs.make_dirs(STORE_DIR)
    rig.rig.fs.write_atomic(STORE_DIR + "\\store.json", b"{not json")
    result = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.code_of(result) == "STORE_CORRUPT"


class _LockedFs(MemoryFileSystem):
    """A file system whose drawings cannot be read (SOLIDWORKS holds them)."""

    def read_bytes(self, path: str) -> bytes:
        if path.lower().endswith(".slddrw"):
            raise PermissionError(path)
        return super().read_bytes(path)


def test_check_drawing_unreadable_file_is_a_catalogued_error() -> None:
    rig = make_tool_rig(fs=_LockedFs())
    rig.write_drawing(DRAWING, CONTENT)
    result = rig.call("check_drawing", {"path": DRAWING})
    assert ToolRig.code_of(result) in CATALOGUED
    assert rig.rig.store().list_job_ids() == ()


BAD_ARGUMENTS: list[JsonValue] = [
    {},
    {"path": None},
    {"path": 5},
    {"path": 1.5},
    {"path": True},
    {"path": ["C:\\Work\\a.slddrw"]},
    {"path": {"p": 1}},
    {"path": ""},
    {"path": "x" * 40_000},
    {"path": DRAWING, "sheets": []},
    {"path": DRAWING, "sheets": ["A", "A"]},
    {"path": DRAWING, "sheets": [""]},
    {"path": DRAWING, "sheets": [1]},
    {"path": DRAWING, "sheets": "Sheet1"},
    {"path": DRAWING, "sheets": None},
    {"path": DRAWING, "sheets": [f"S{i}" for i in range(65)]},
    {"path": DRAWING, "sheets": [["A"]]},
    {"path": DRAWING, "drawing_intent": {}},
    {"path": DRAWING, "detail": "full"},
    {"path": float("nan")},
]


@pytest.mark.parametrize("arguments", BAD_ARGUMENTS)
def test_check_drawing_bad_arguments_return_schema_invalid(arguments: JsonValue) -> None:
    rig = _ready()
    result = rig.call("check_drawing", arguments)
    assert ToolRig.code_of(result) == "IR_SCHEMA_INVALID"
    assert rig.rig.store().list_job_ids() == ()


ODD_PATHS = [
    "C:\\Work\\ünïcödé\u202e.slddrw",
    "C:\\Work\\日本語.slddrw",
    "C:\\Work\\a.slddrw\x00",
    "C:\\Work\\\x00a.slddrw",
    "C:\\Work\\a.slddrw ",
    "C:\\Work\\a.slddrw.",
    "C:\\Work\\a.slddrw::$DATA",
    "C:\\Work\\..\\..\\Windows\\a.slddrw",
    "C:\\Work\\sub\\..\\a.slddrw\\",
    "C:/Work/a.slddrw",
    "c:\\work\\A.SLDDRW",
    "\\\\server\\share\\a.slddrw",
    "\\\\?\\C:\\Work\\a.slddrw",
    "\\\\.\\C:\\Work\\a.slddrw",
    "~\\a.slddrw",
    "%USERPROFILE%\\a.slddrw",
    "$HOME\\a.slddrw",
    "C:a.slddrw",
    "C:\\",
    "C:\\Work\\" + "a" * 300 + ".slddrw",
    "NUL.slddrw",
    "C:\\Work\\con.slddrw",
    " ",
    "\n",
    "\ud800.slddrw",
]


@pytest.mark.parametrize("path", ODD_PATHS)
def test_check_drawing_odd_paths_never_raise(path: str) -> None:
    rig = _ready()
    result = rig.call("check_drawing", {"path": path})
    code = ToolRig.code_of(result)
    if code is not None:
        assert code in CATALOGUED
    else:
        # accepted paths must be real files below the allowed root
        assert rig.rig.store().list_job_ids() != ()


def test_unreadable_or_odd_path_message_does_not_echo_environment_values() -> None:
    rig = _ready()
    result = rig.call("check_drawing", {"path": "%SECRET_TOKEN%\\a.slddrw"})
    assert ToolRig.code_of(result) == "AUTH_PATH_DENIED"
    assert "SECRET_VALUE" not in str(result.envelope)
