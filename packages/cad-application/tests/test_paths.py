"""Path policy: authorize() over the FileSystem port (spec 12.5)."""

from dataclasses import dataclass, field

import pytest
from cad_application.config import Settings
from cad_application.paths import Authorized, ToolError, authorize
from cad_application.testing.memory_fs import MemoryFileSystem

ROOT = "C:\\Work"
LOCAL = "C:\\Users\\me\\AppData\\Local"
# sha256 of the UTF-8 bytes of "c:\vault" (normcase of "C:\Vault"), computed independently.
VAULT_HASH = "dc75125ce6632b8975f621f208fbc9e5e6991e2e39670675d8bce13549ac6463"


@dataclass
class Case:
    path: str
    roots: tuple[str, ...] = (ROOT,)
    reason: str | None = None
    junctions: dict[str, str] = field(default_factory=dict[str, str])


def _fs(junctions: dict[str, str] | None = None) -> MemoryFileSystem:
    fs = MemoryFileSystem(junctions=junctions)
    for path in (
        "C:\\Work\\a.slddrw",
        "C:\\Other\\a.slddrw",
        "D:\\Elsewhere\\a.slddrw",
        "C:\\a\\f.slddrw",
        "C:\\ab\\f.slddrw",
        "C:\\Work\\Prices$USD\\a.slddrw",
        "\\\\srv\\share\\dir\\a.slddrw",
    ):
        parent = path.rsplit("\\", 1)[0]
        fs.make_dirs(parent)
        fs.write_atomic(path, b"x")
    return fs


def _settings(roots: tuple[str, ...] = (ROOT,), vaults: tuple[str, ...] = ()) -> Settings:
    return Settings(allowed_roots=roots, pdm_vault_roots=vaults, local_app_data=LOCAL)


CASES = {
    "relative": Case("a.slddrw", reason="not_absolute"),
    "rooted_without_drive": Case("\\Work\\a.slddrw", reason="not_absolute"),
    "drive_relative": Case("C:a.slddrw", reason="not_absolute"),
    "home": Case("~\\a.slddrw", reason="home_or_env"),
    "percent_var": Case("%USERPROFILE%\\a.slddrw", reason="home_or_env"),
    "dollar_var": Case("$env:HOME\\a.slddrw", reason="home_or_env"),
    "dollar_var_uppercase": Case("C:\\Work\\$ENV:X\\a.slddrw", reason="home_or_env"),
    "paren_var": Case("C:\\Work\\$(X)\\a.slddrw", reason="home_or_env"),
    "bare_dollar_is_not_absolute": Case("$HOME\\a.slddrw", reason="not_absolute"),
    "stream": Case("C:\\Work\\a.slddrw:x.slddrw", reason="stream"),
    "stream_in_folder": Case("C:\\Work\\a.slddrw:x\\b.slddrw", reason="stream"),
    "store_junction_leaves_root": Case(
        "C:\\Work\\a.slddrw",
        reason="store_outside_roots",
        junctions={"C:\\Work\\.cad": "D:\\Elsewhere"},
    ),
    "braced_var": Case("C:\\Work\\${X}\\a.slddrw", reason="home_or_env"),
    "extended_prefix": Case("\\\\?\\C:\\Work\\a.slddrw", reason="device_prefix"),
    "device_prefix": Case("\\\\.\\C:\\Work\\a.slddrw", reason="device_prefix"),
    "slash_device_prefix": Case("//?/C:/Work/a.slddrw", reason="device_prefix"),
    "dotdot_escapes_root": Case("C:\\Work\\..\\Other\\a.slddrw", reason="outside_roots"),
    "junction_leaves_root": Case(
        "C:\\Work\\link\\a.slddrw",
        reason="outside_roots",
        junctions={"C:\\Work\\link": "D:\\Elsewhere"},
    ),
    "other_drive": Case("D:\\Elsewhere\\a.slddrw", reason="outside_roots"),
    "root_prefix_of_sibling": Case("C:\\ab\\f.slddrw", roots=("C:\\a",), reason="outside_roots"),
    "unc_without_unc_root": Case("\\\\srv\\share\\dir\\a.slddrw", reason="unc_not_allowed"),
    "no_roots": Case("C:\\Work\\a.slddrw", roots=(), reason="no_roots"),
    "plain_ok": Case("C:\\Work\\a.slddrw"),
    "dollar_in_folder_name": Case("C:\\Work\\Prices$USD\\a.slddrw"),
    "store_junction_inside_root": Case(
        "C:\\Work\\a.slddrw", junctions={"C:\\Work\\.cad": "C:\\Work\\store"}
    ),
    "case_only_difference": Case("c:\\WORK\\A.SLDDRW"),
    "forward_slashes": Case("C:/Work/a.slddrw"),
    "dotdot_inside_root": Case("C:\\Work\\x\\..\\a.slddrw"),
    "root_is_prefix_but_boundary_ok": Case("C:\\a\\f.slddrw", roots=("C:\\a",)),
    "unc_with_unc_root": Case("\\\\srv\\share\\dir\\a.slddrw", roots=("\\\\srv\\share",)),
    "lower_case_root": Case("C:\\Work\\a.slddrw", roots=("c:\\work",)),
    "root_with_trailing_slash": Case("C:\\Work\\a.slddrw", roots=("C:\\Work\\",)),
}


@pytest.mark.parametrize("case", CASES.values(), ids=list(CASES))
def test_authorize_cases(case: Case) -> None:
    result = authorize(case.path, _settings(case.roots), _fs(case.junctions))
    if case.reason is None:
        assert isinstance(result, Authorized), result
        return
    assert isinstance(result, ToolError)
    assert result.code == "AUTH_PATH_DENIED"
    assert result.details == {"reason": case.reason}


def test_authorized_path_is_normalised_with_stored_case() -> None:
    result = authorize("c:\\WORK\\x\\..\\A.SLDDRW", _settings(), _fs())
    assert isinstance(result, Authorized)
    assert result.path == "C:\\Work\\a.slddrw"
    assert result.root == "C:\\Work"


def test_project_is_nearest_store_up_to_root() -> None:
    fs = _fs()
    fs.make_dirs("C:\\Work\\p1\\.cad")
    fs.make_dirs("C:\\Work\\p1\\sub")
    fs.write_atomic("C:\\Work\\p1\\sub\\b.slddrw", b"x")
    fs.make_dirs("C:\\.cad")  # above the allowed root: never considered
    result = authorize("C:\\Work\\p1\\sub\\b.slddrw", _settings(), fs)
    assert isinstance(result, Authorized)
    assert result.project_root == "C:\\Work\\p1"
    assert result.store_dir == "C:\\Work\\p1\\.cad"
    assert not result.in_vault
    above = authorize("C:\\Work\\a.slddrw", _settings(), fs)
    assert isinstance(above, Authorized)
    assert above.project_root == ROOT


def test_project_defaults_to_root() -> None:
    result = authorize("C:\\Work\\a.slddrw", _settings(), _fs())
    assert isinstance(result, Authorized)
    assert (result.project_root, result.store_dir) == (ROOT, "C:\\Work\\.cad")


def test_vault_store_goes_to_local_app_data() -> None:
    fs = MemoryFileSystem()
    fs.make_dirs("C:\\Vault\\parts")
    fs.write_atomic("C:\\Vault\\parts\\a.slddrw", b"x")
    settings = _settings(roots=("C:\\Vault",), vaults=("C:\\Vault",))
    result = authorize("C:\\Vault\\parts\\a.slddrw", settings, fs)
    assert isinstance(result, Authorized)
    assert result.in_vault
    assert result.project_root == "C:\\Vault"
    assert result.store_dir == f"{LOCAL}\\sw-mcp\\stores\\{VAULT_HASH}"


def test_missing_file_is_file_not_found() -> None:
    result = authorize("C:\\Work\\none.slddrw", _settings(), _fs())
    assert isinstance(result, ToolError)
    assert result.code == "FILE_NOT_FOUND"
    missing_parent = authorize("C:\\Work\\nodir\\none.slddrw", _settings(), _fs())
    assert isinstance(missing_parent, ToolError)
    assert missing_parent.code == "FILE_NOT_FOUND"
    outside = authorize("C:\\Elsewhere\\nodir\\none.slddrw", _settings(), _fs())
    assert isinstance(outside, ToolError)
    assert outside.code == "AUTH_PATH_DENIED"  # no existence leak outside the roots


def test_directory_is_not_a_file() -> None:
    fs = _fs()
    result = authorize("C:\\Work", _settings(), fs)
    assert isinstance(result, ToolError)
    assert result.code == "FILE_NOT_FOUND"
    as_dir = authorize("C:\\Work", _settings(), fs, expect="dir")
    assert isinstance(as_dir, Authorized)
    file_as_dir = authorize("C:\\Work\\a.slddrw", _settings(), fs, expect="dir")
    assert isinstance(file_as_dir, ToolError)
    assert file_as_dir.code == "FILE_NOT_FOUND"


def test_suffix_case_insensitive() -> None:
    fs = _fs()
    assert isinstance(
        authorize("C:\\Work\\a.slddrw", _settings(), fs, suffix=".SLDDRW"), Authorized
    )
    assert isinstance(
        authorize("C:\\Work\\a.slddrw", _settings(), fs, suffix=".slddrw"), Authorized
    )
    wrong = authorize("C:\\Work\\a.slddrw", _settings(), fs, suffix=".sldprt")
    assert isinstance(wrong, ToolError)
    assert wrong.code == "IR_SCHEMA_INVALID"
    assert wrong.details == {"reason": "suffix"}


def test_message_does_not_echo_env_values() -> None:
    for path in ("%SECRET_TOKEN%\\a.slddrw", "$SECRET_TOKEN\\a.slddrw", "~\\SECRET_TOKEN"):
        result = authorize(path, _settings(), _fs())
        assert isinstance(result, ToolError)
        assert "SECRET_TOKEN" not in result.message
        assert "SECRET_TOKEN" not in repr(result.details)
    no_roots = authorize("C:\\Work\\a.slddrw", _settings(roots=()), _fs())
    assert isinstance(no_roots, ToolError)
    assert "access.allowed_roots" in no_roots.message
