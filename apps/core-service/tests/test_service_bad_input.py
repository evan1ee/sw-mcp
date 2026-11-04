"""Bad input at the boundaries: every case answers a catalogued error, none raises."""

from collections.abc import Callable
from pathlib import Path

import pytest
from cad_application.config.settings import ConfigError
from cad_application.testing.fakes import FakeBackend, FakeBackendProvider, make_hello
from cad_application.tools.registry import UnknownTool
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.error_codes import ErrorCode
from core_service.providers import ReplayBackendProvider
from core_service.service import CoreService
from core_service.testing import ServiceRig

type RigFactory = Callable[..., ServiceRig]

CATALOGUE = {code.value for code in ErrorCode}
TOOLS = ("check_drawing", "get_drawing_report", "get_execution_status", "cancel_execution")


def _idle(start_rig: RigFactory, **kwargs: object) -> ServiceRig:
    return start_rig(provider=FakeBackendProvider(FakeBackend(make_hello())), **kwargs)


def _code(rig: ServiceRig, name: object, arguments: object) -> str:
    result = rig.service.call_tool(name, arguments)  # type: ignore[arg-type]
    assert isinstance(result.envelope, dict)
    code = rig.error_code(result.envelope)
    assert code in CATALOGUE
    assert "\n" not in result.summary
    return code


def test_unknown_tool_is_a_protocol_error(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    with pytest.raises(UnknownTool):
        rig.service.call_tool("delete_everything", {})


@pytest.mark.parametrize("name", [None, 5, "", " ", "check_drawing\x00", ["check_drawing"], b"x"])
def test_odd_tool_names_are_unknown_tools(start_rig: RigFactory, name: object) -> None:
    with pytest.raises(UnknownTool):
        _idle(start_rig).service.call_tool(name, {})


def test_unexpected_exception_is_raised_not_answered(
    start_rig: RigFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _idle(start_rig)

    def boom(*_: object) -> None:
        raise ValueError("defect")

    monkeypatch.setattr(rig.service._registry, "call", boom)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ValueError, match="defect"):
        rig.service.call_tool("check_drawing", {})


def test_os_error_is_store_unavailable(
    start_rig: RigFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _idle(start_rig)

    def boom(*_: object) -> None:
        raise OSError("disk")

    monkeypatch.setattr(rig.service._registry, "call", boom)  # pyright: ignore[reportPrivateUsage]
    result = rig.service.call_tool("check_drawing", {})
    assert isinstance(result.envelope, dict)
    assert rig.error_code(result.envelope) == "STORE_UNAVAILABLE"
    error = result.envelope["error"]
    assert isinstance(error, dict)
    assert error["details"] == {"reason": "io_error"}


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("arguments", [None, 5, "x", [], [1], True, 1.5])
def test_non_object_arguments_are_schema_invalid(
    start_rig: RigFactory, tool: str, arguments: object
) -> None:
    assert _code(_idle(start_rig), tool, arguments) == "IR_SCHEMA_INVALID"


def _nested(depth: int) -> JsonValue:
    value: JsonValue = "x"
    for _ in range(depth):
        value = {"a": value}
    return value


@pytest.mark.parametrize(
    "arguments",
    [
        {1: 2},
        {"path": float("nan")},
        {"path": ["C:\\x.slddrw"]},
        {"path": None},
        {"path": "C:\\x.slddrw", "sheets": "Sheet1"},
        {"path": "C:\\x.slddrw", "sheets": [1, None]},
        {"path": "C:\\x.slddrw", "drawing_intent": {}},
        {"path": "x" * 200_000},
        _nested(50_000),
    ],
)
def test_malformed_arguments_give_a_catalogued_error(
    start_rig: RigFactory, arguments: object
) -> None:
    _code(_idle(start_rig), "check_drawing", arguments)


@pytest.mark.parametrize("tool", ["get_execution_status", "cancel_execution"])
@pytest.mark.parametrize("identifier", ["", "job_", "nope", "job_" + "0" * 26, "rep_" + "0" * 26])
def test_malformed_and_unknown_job_ids(start_rig: RigFactory, tool: str, identifier: str) -> None:
    code = _code(_idle(start_rig), tool, {"execution_id": identifier})
    assert code in {"IR_SCHEMA_INVALID", "EXEC_NOT_FOUND"}


@pytest.mark.parametrize("identifier", ["", "rep_", "x", "rep_" + "0" * 26, "job_" + "0" * 26])
def test_malformed_and_unknown_report_ids(start_rig: RigFactory, identifier: str) -> None:
    code = _code(_idle(start_rig), "get_drawing_report", {"report_id": identifier})
    assert code in {"IR_SCHEMA_INVALID", "EXEC_NOT_FOUND"}


def _odd_paths(project: Path) -> list[str]:
    here = str(project)
    return [
        "",
        "   ",
        "a.slddrw",
        "C:a.slddrw",
        "\\\\?\\" + here + "\\a.slddrw",
        "\\\\server\\share\\a.slddrw",
        "~\\a.slddrw",
        "%APPDATA%\\a.slddrw",
        here + "\\..\\..\\a.slddrw",
        "C:\\Work\\\ud800.slddrw",
        here + "\\\ud800.slddrw",
        here + "\\a\x00.slddrw",
        here + "\\" + "x" * 40_000 + ".slddrw",
        here + "\\a.slddrw:stream",
        here + "\\con.slddrw",
        here + "\\missing.slddrw",
        here,
    ]


def test_odd_drawing_paths_are_denied_or_not_found(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    for path in _odd_paths(rig.project):
        code = _code(rig, "check_drawing", {"path": path})
        assert code in {"AUTH_PATH_DENIED", "FILE_NOT_FOUND", "IR_SCHEMA_INVALID"}, repr(path[-40:])


def test_unicode_drawing_path_commits(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_owned", name="图纸 ünï ☃ (1).slddrw")
    final = rig.wait_final(rig.submit())
    assert final["state"] == "COMMITTED"


def test_directory_named_like_a_drawing_is_file_not_found(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    (rig.project / "folder.slddrw").mkdir()
    code = _code(rig, "check_drawing", {"path": str(rig.project / "folder.slddrw")})
    assert code == "FILE_NOT_FOUND"


def test_store_locked_by_another_service(start_rig: RigFactory) -> None:
    first = _idle(start_rig)
    first.wait_final(first.submit())  # opens the store
    second = _idle(start_rig)
    assert _code(second, "check_drawing", {"path": second.drawing}) == "STORE_LOCKED"


def test_unwritable_store_folder_is_store_unavailable(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    (rig.project / ".cad" / ".lock").mkdir(parents=True)  # a folder where the lock file goes
    assert _code(rig, "check_drawing", {"path": rig.drawing}) == "STORE_UNAVAILABLE"


def test_store_folder_that_is_a_file_is_store_unavailable(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    (rig.project / ".cad").write_bytes(b"not a folder")
    assert _code(rig, "check_drawing", {"path": rig.drawing}) == "STORE_UNAVAILABLE"


@pytest.mark.parametrize("content", [b"", b"garbage", b"\x00\xff\xfe", b'{"store_version": "9.0"}'])
def test_corrupt_store_manifest_is_store_corrupt(start_rig: RigFactory, content: bytes) -> None:
    rig = _idle(start_rig)
    (rig.project / ".cad").mkdir()
    (rig.project / ".cad" / "store.json").write_bytes(content)
    assert _code(rig, "check_drawing", {"path": rig.drawing}) == "STORE_CORRUPT"


@pytest.mark.parametrize(
    "content", [b"", b"\x00\xff", b"broken = [", b'config_version = "1.0"\nx = 1\n']
)
def test_corrupt_project_config_is_config_invalid(start_rig: RigFactory, content: bytes) -> None:
    rig = _idle(start_rig)
    (rig.project / ".cad").mkdir()
    (rig.project / ".cad" / "config.toml").write_bytes(content)
    assert _code(rig, "check_drawing", {"path": rig.drawing}) == "CONFIG_INVALID"


def test_missing_transcript_fails_the_job_with_backend_lost(
    start_rig: RigFactory, tmp_path: Path
) -> None:
    rig = start_rig(provider=ReplayBackendProvider.from_file(str(tmp_path / "missing.jsonl")))
    final = rig.wait_final(rig.submit())
    error = final["error"]
    assert final["state"] == "FAILED"
    assert isinstance(error, dict)
    assert error["code"] == "BACKEND_LOST"


def test_start_refuses_an_invalid_user_file(tmp_path: Path) -> None:
    project, _ = ServiceRig.prepare(tmp_path)
    (tmp_path / "appdata" / "sw-mcp" / "config.toml").write_bytes(b"\x00\xff garbage")
    started = CoreService.start(
        install_root=str(tmp_path / "install"),
        environ=ServiceRig.environment(tmp_path),
        provider=FakeBackendProvider(None),
    )
    assert isinstance(started, ConfigError)
    assert started.code == "CONFIG_INVALID"
    assert project.exists()


def test_start_refuses_a_garbage_environment_value(tmp_path: Path) -> None:
    ServiceRig.prepare(tmp_path)
    environ = {**ServiceRig.environment(tmp_path), "SWMCP_CORE__JOB_RETENTION_DAYS": "S3CRET-x"}
    started = CoreService.start(
        install_root=str(tmp_path / "install"),
        environ=environ,
        provider=FakeBackendProvider(None),
    )
    assert isinstance(started, ConfigError)
    assert "S3CRET" not in started.message


def test_start_accepts_a_user_file_with_bom(tmp_path: Path) -> None:
    ServiceRig.prepare(tmp_path)
    path = tmp_path / "appdata" / "sw-mcp" / "config.toml"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    started = CoreService.start(
        install_root=str(tmp_path / "install"),
        environ=ServiceRig.environment(tmp_path),
        provider=FakeBackendProvider(None),
    )
    assert isinstance(started, CoreService)
    started.stop()


def test_unencodable_sheet_name_is_a_catalogued_error(start_rig: RigFactory) -> None:
    rig = _idle(start_rig)
    code = _code(rig, "check_drawing", {"path": rig.drawing, "sheets": ["\ud800"]})
    assert code == "IR_SCHEMA_INVALID"
    # Nothing was queued: the store has no job folder for it.
    jobs = rig.project / ".cad" / "jobs"
    assert not jobs.exists() or [p for p in jobs.iterdir() if (p / "job.json").exists()] == []


def test_sheet_names_with_unicode_are_fine(start_rig: RigFactory) -> None:
    rig = start_rig("check_drawing_owned")
    data = rig.data(rig.call("check_drawing", {"path": rig.drawing, "sheets": ["图纸1", "ü ☃"]}))
    assert str(data["execution_id"]).startswith("job_")
