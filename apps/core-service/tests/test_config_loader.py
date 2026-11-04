"""Reading the user file, the environment and project files into Settings (13.3.1, 13.3.2)."""

from collections.abc import Mapping

import pytest
from cad_application.config.settings import ConfigError, Settings
from cad_application.testing.memory_fs import MemoryFileSystem
from core_service.config_loader import CoreConfig, ProjectSettings, load_core_config

INSTALL = "C:\\Install"
APPDATA = "C:\\Users\\u\\AppData\\Roaming"
LOCAL = "C:\\Users\\u\\AppData\\Local"
USER_FILE = APPDATA + "\\sw-mcp\\config.toml"
ENV = {"APPDATA": APPDATA, "LOCALAPPDATA": LOCAL}
HEAD = 'config_version = "1.0"\n'


def _fs(user_file: bytes | None = None) -> MemoryFileSystem:
    fs = MemoryFileSystem()
    if user_file is not None:
        fs.make_dirs(APPDATA + "\\sw-mcp")
        fs.write_atomic(USER_FILE, user_file)
    return fs


def _config(fs: MemoryFileSystem, environ: Mapping[str, str] = ENV) -> CoreConfig:
    loaded = load_core_config(fs, environ, INSTALL)
    assert isinstance(loaded, CoreConfig), loaded
    return loaded


def _error(fs: MemoryFileSystem, environ: Mapping[str, str] = ENV) -> ConfigError:
    loaded = load_core_config(fs, environ, INSTALL)
    assert isinstance(loaded, ConfigError), loaded
    return loaded


def test_user_file_and_env_layers() -> None:
    user = HEAD + '[access]\nallowed_roots = ["C:\\\\Work"]\n[core]\njob_retention_days = 3\n'
    fs = _fs(user.encode())
    env = {**ENV, "SWMCP_CORE__JOB_RETENTION_DAYS": "9", "SWMCP_LOGGING__LEVEL": '"debug"'}
    settings = _config(fs, env).settings
    assert settings.allowed_roots == ("C:\\Work",)
    assert settings.job_retention_days == 9  # noqa: PLR2004 - the environment wins over the file
    assert settings.logging_level == "debug"


def test_missing_user_file_gives_defaults_and_no_access() -> None:
    config = _config(_fs())
    assert config.settings.allowed_roots == ()
    assert config.settings.job_retention_days == Settings().job_retention_days


def test_standard_dir_resolved_against_install_root() -> None:
    config = _config(_fs())
    assert config.settings.standard_dir == "C:\\Install\\standards\\iso"
    assert config.settings.local_app_data == LOCAL


def test_absolute_standard_dir_from_user_file_is_kept() -> None:
    user = HEAD + "[drawing]\nstandard_dir = 'D:\\Std\\iso'\n"
    assert _config(_fs(user.encode())).settings.standard_dir == "D:\\Std\\iso"


def test_user_file_with_bom_is_accepted() -> None:
    user = "\ufeff" + HEAD + "[core]\njob_retention_days = 4\n"
    assert _config(_fs(user.encode("utf-8"))).settings.job_retention_days == 4  # noqa: PLR2004


@pytest.mark.parametrize(
    ("content", "why"),
    [
        (b"", "empty"),
        (b"   \r\n", "blank"),
        (b"\x00\x01\xff\xfe binary \x80", "binary"),
        (b"config_version = 'unterminated", "syntax"),
        (b'config_version = "1.0"\nunknown_key = 1\n', "unknown key"),
        (b'config_version = "1.0"\n[core]\njob_retention_days = "x"\n', "wrong type"),
        (b'config_version = "2.0"\n', "wrong version"),
        ("\ud83d".encode("utf-16-le", "surrogatepass"), "utf-16 noise"),
    ],
)
def test_corrupt_user_file_is_config_invalid_naming_the_file(content: bytes, why: str) -> None:
    error = _error(_fs(content))
    assert error.code == "CONFIG_INVALID", why
    assert error.origin == USER_FILE


def test_garbage_env_value_is_config_invalid_and_not_echoed() -> None:
    env = {**ENV, "SWMCP_CORE__JOB_RETENTION_DAYS": "not-a-number-S3CRET"}
    error = _error(_fs(), env)
    assert error.code == "CONFIG_INVALID"
    assert "S3CRET" not in error.message
    assert "S3CRET" not in str(error.key)


def test_env_unknown_key_is_config_invalid() -> None:
    assert _error(_fs(), {**ENV, "SWMCP_NOPE__X": "1"}).code == "CONFIG_INVALID"


def test_missing_local_app_data_is_config_invalid() -> None:
    error = _error(_fs(), {"APPDATA": APPDATA})
    assert error.key == "LOCALAPPDATA"


def test_relative_local_app_data_is_config_invalid() -> None:
    assert _error(_fs(), {**ENV, "LOCALAPPDATA": "relative\\dir"}).key == "LOCALAPPDATA"


def _project(
    fs: MemoryFileSystem, text: bytes | None, user: bytes | None = None
) -> ProjectSettings:
    config = _config(_fs(user) if user is not None else fs)
    if text is not None:
        fs.make_dirs("C:\\Work\\.cad")
        fs.write_atomic("C:\\Work\\.cad\\config.toml", text)
    return ProjectSettings(fs, config)


def test_project_file_overrides_user_values() -> None:
    fs = _fs((HEAD + "[core]\njob_retention_days = 3\n").encode())
    project = _project(fs, (HEAD + "[core]\njob_retention_days = 5\n").encode())
    found = project("C:\\Work")
    assert isinstance(found, Settings)
    assert found.job_retention_days == 5  # noqa: PLR2004


def test_env_beats_project_file() -> None:
    fs = _fs()
    config = _config(fs, {**ENV, "SWMCP_CORE__JOB_RETENTION_DAYS": "11"})
    fs.make_dirs("C:\\Work\\.cad")
    fs.write_atomic(
        "C:\\Work\\.cad\\config.toml", (HEAD + "[core]\njob_retention_days = 5\n").encode()
    )
    found = ProjectSettings(fs, config)("C:\\Work")
    assert isinstance(found, Settings)
    assert found.job_retention_days == 11  # noqa: PLR2004


def test_project_security_keys_are_ignored_with_a_warning() -> None:
    fs = _fs((HEAD + "[access]\nallowed_roots = ['C:\\Work']\n").encode())
    text = (
        HEAD + "[access]\nallowed_roots = ['C:\\Elsewhere']\n[drawing]\nstandard_dir = 'C:\\Evil'\n"
    )
    found = _project(fs, text.encode())("C:\\Work")
    assert isinstance(found, Settings)
    assert found.allowed_roots == ("C:\\Work",)
    assert found.standard_dir == "C:\\Install\\standards\\iso"
    assert found.warnings


def test_missing_project_file_gives_user_settings() -> None:
    fs = _fs()
    found = _project(fs, None)("C:\\Work")
    assert isinstance(found, Settings)
    assert found.local_app_data == LOCAL


@pytest.mark.parametrize("content", [b"", b"\x00\xff\xfe", b"config_version = ", b"zzz = 1\n"])
def test_corrupt_project_file_is_config_invalid(content: bytes) -> None:
    fs = _fs()
    found = _project(fs, content)("C:\\Work")
    assert isinstance(found, ConfigError)
    assert found.code == "CONFIG_INVALID"
    assert found.origin == "C:\\Work\\.cad\\config.toml"


def test_project_file_is_read_again_when_it_changes() -> None:
    fs = _fs()
    project = _project(fs, (HEAD + "[core]\njob_retention_days = 5\n").encode())
    first = project("C:\\Work")
    fs.write_atomic(
        "C:\\Work\\.cad\\config.toml", (HEAD + "[core]\njob_retention_days = 6\n").encode()
    )
    second = project("C:\\Work")
    assert isinstance(first, Settings)
    assert isinstance(second, Settings)
    assert (first.job_retention_days, second.job_retention_days) == (5, 6)
    fs.write_atomic("C:\\Work\\.cad\\config.toml", b"broken = [")
    assert isinstance(project("C:\\Work"), ConfigError)


def test_unreadable_project_file_is_config_invalid() -> None:
    fs = _fs()
    project = _project(fs, None)
    fs.make_dirs("C:\\Work\\.cad\\config.toml")  # a folder where the file should be
    found = project("C:\\Work")
    assert isinstance(found, ConfigError)
    assert found.code == "CONFIG_INVALID"
