"""Configuration layers, precedence and validation (spec 13.3)."""

from dataclasses import asdict

from cad_application.config import (
    ConfigError,
    Layer,
    Settings,
    merge_settings,
    parse_env_layer,
    parse_toml_layer,
)
from cad_drawing.checks import CheckThresholds

USER = "C:\\Users\\me\\AppData\\Roaming\\sw-mcp\\config.toml"
PROJECT = "C:\\work\\proj\\.cad\\config.toml"


def _user(text: str) -> Layer:
    layer = parse_toml_layer(text, source="user", origin=USER)
    assert isinstance(layer, Layer), layer
    return layer


def _project(text: str) -> Layer:
    layer = parse_toml_layer(text, source="project", origin=PROJECT)
    assert isinstance(layer, Layer), layer
    return layer


def _settings(*layers: Layer) -> Settings:
    settings = merge_settings(layers)
    assert isinstance(settings, Settings), settings
    return settings


def _error(*layers: Layer) -> ConfigError:
    result = merge_settings(layers)
    assert isinstance(result, ConfigError), result
    return result


def test_defaults_match_13_3_3() -> None:
    settings = _settings()
    assert settings.allowed_roots == ()
    assert settings.pdm_vault_roots == ()
    assert settings.toolsets == ("core",)
    assert settings.part_template == ""
    assert settings.idle_shutdown_min == 30  # noqa: PLR2004
    assert settings.job_retention_days == 7  # noqa: PLR2004
    assert settings.solidworks_session == "auto"
    assert settings.command_timeout_s == 120  # noqa: PLR2004
    assert settings.read_timeout_s == 30  # noqa: PLR2004
    assert settings.ui_blocked_s == 30  # noqa: PLR2004
    assert settings.heartbeat_s == 10  # noqa: PLR2004
    assert settings.job_timeout_min == 10  # noqa: PLR2004
    assert settings.relayout_max_iterations == 8  # noqa: PLR2004
    assert settings.pin_threshold_mm == 0.5  # noqa: PLR2004
    assert settings.epsilon_mm == 0.01  # noqa: PLR2004
    assert settings.text_clearance_mm == 0.5  # noqa: PLR2004
    assert settings.line_clearance_mm == 0.25  # noqa: PLR2004
    assert settings.edge_clearance_mm == 0.25  # noqa: PLR2004
    assert settings.font_metric_margin == 0.1  # noqa: PLR2004
    assert settings.parallel_deg == 0.01  # noqa: PLR2004
    assert settings.standard_dir == "standards\\iso"
    assert settings.snapshot_keep == 10  # noqa: PLR2004
    assert settings.backup_keep == 5  # noqa: PLR2004
    assert settings.logging_level == "info"
    assert settings.logging_retention_days == 14  # noqa: PLR2004
    assert settings.warnings == ()


def test_precedence_defaults_user_project_env() -> None:
    user = _user(
        'config_version = "1.0"\n[core]\njob_retention_days = 3\nidle_shutdown_min = 5\n'
        "[drawing.check]\nepsilon_mm = 0.02\n"
    )
    project = _project(
        'config_version = "1.0"\n[core]\njob_retention_days = 2\n[store]\nsnapshot_keep = 4\n'
    )
    env = parse_env_layer({"SWMCP_CORE__JOB_RETENTION_DAYS": "1", "PATH": "x"})
    settings = _settings(user, project, env)
    assert settings.job_retention_days == 1  # env beats project beats user
    assert settings.idle_shutdown_min == 5  # noqa: PLR2004  # only the user file says
    assert settings.snapshot_keep == 4  # noqa: PLR2004  # only the project says
    assert settings.epsilon_mm == 0.02  # noqa: PLR2004
    assert settings.heartbeat_s == 10  # noqa: PLR2004  # nobody says: the default
    assert _settings(user, project).job_retention_days == 2  # noqa: PLR2004


def test_security_keys_only_from_user_file() -> None:
    user = _user(
        'config_version = "1.0"\n[access]\nallowed_roots = ["C:\\\\work"]\n'
        '[drawing]\nstandard_dir = "C:\\\\std"\n[solidworks]\nsession = 42\n'
    )
    project = _project(
        'config_version = "1.0"\n[access]\nallowed_roots = ["D:\\\\everything"]\n'
        'pdm_vault_roots = ["D:\\\\vault"]\n[drawing]\nstandard_dir = "D:\\\\mine"\n'
        "[solidworks]\nsession = 7\ncommand_timeout_s = 60\n"
    )
    env = parse_env_layer(
        {
            "SWMCP_ACCESS__ALLOWED_ROOTS": '["E:\\\\x"]',
            "SWMCP_SOLIDWORKS__SESSION": "9",
            "SWMCP_DRAWING__STANDARD_DIR": '"E:\\\\y"',
        }
    )
    settings = _settings(user, project, env)
    assert settings.allowed_roots == ("C:\\work",)
    assert settings.pdm_vault_roots == ()
    assert settings.standard_dir == "C:\\std"
    assert settings.solidworks_session == 42  # noqa: PLR2004
    assert settings.command_timeout_s == 60  # noqa: PLR2004  # a non-security key still applies
    joined = "\n".join(settings.warnings)
    assert "access.allowed_roots" in joined
    assert "access.pdm_vault_roots" in joined
    assert "drawing.standard_dir" in joined
    assert "solidworks.session" in joined
    assert "D:" not in joined
    assert "E:" not in joined
    assert len(settings.warnings) == 7  # noqa: PLR2004  # 4 from the project, 3 from the env


def test_unknown_key_names_file_and_key() -> None:
    error = _error(_user('config_version = "1.0"\n[drawing.check]\nepsilon = 0.01\n'))
    assert error.code == "CONFIG_INVALID"
    assert error.origin == USER
    assert error.key == "drawing.check.epsilon"
    assert error.line is None
    assert "epsilon" in error.message


def test_wrong_type_names_key() -> None:
    error = _error(_project('config_version = "1.0"\n[core]\nidle_shutdown_min = "30"\n'))
    assert error.origin == PROJECT
    assert error.key == "core.idle_shutdown_min"
    assert "integer" in error.message
    assert '"30"' not in error.message  # values are never echoed (G3)


def test_missing_config_version_is_named() -> None:
    error = _error(_user("[core]\nidle_shutdown_min = 3\n"))
    assert error.key == "config_version"


def test_syntax_error_names_line() -> None:
    result = parse_toml_layer(
        'config_version = "1.0"\n[core\nidle = 1\n', source="user", origin=USER
    )
    assert isinstance(result, ConfigError)
    assert result.origin == USER
    assert result.line == 2  # noqa: PLR2004
    assert result.code == "CONFIG_INVALID"


def test_env_values_parsed_as_toml() -> None:
    layer = parse_env_layer(
        {
            "SWMCP_CORE__IDLE_SHUTDOWN_MIN": "60",
            "SWMCP_DRAWING__CHECK__EPSILON_MM": "0.05",
            "SWMCP_MCP__TOOLSETS": '["full"]',
            "SWMCP_LOGGING__LEVEL": '"debug"',
            "SWMCP_STORE__SNAPSHOT_KEEP": "true",
            "SWMCP_DRAWING__STANDARD_DIR": "C:\\plain text",  # not TOML: kept as a string
            "OTHER": "1",
        }
    )
    assert layer.source == "env"
    assert layer.values == {
        "core": {"idle_shutdown_min": 60},
        "drawing": {"check": {"epsilon_mm": 0.05}, "standard_dir": "C:\\plain text"},
        "mcp": {"toolsets": ["full"]},
        "logging": {"level": "debug"},
        "store": {"snapshot_keep": True},
    }


def test_env_error_names_the_variable_not_the_value() -> None:
    error = _error(parse_env_layer({"SWMCP_CORE__IDLE_SHUTDOWN_MIN": "soon-ish"}))
    assert error.origin == "SWMCP_CORE__IDLE_SHUTDOWN_MIN"
    assert error.key == "core.idle_shutdown_min"
    assert "soon-ish" not in error.message
    unknown = _error(parse_env_layer({"SWMCP_CORE__NOPE": "1"}))
    assert unknown.origin == "SWMCP_CORE__NOPE"


def test_thresholds_from_settings() -> None:
    user = _user(
        'config_version = "1.0"\n[drawing.check]\nepsilon_mm = 0.02\ntext_clearance_mm = 1.0\n'
        "line_clearance_mm = 0.3\nedge_clearance_mm = 0.4\nfont_metric_margin = 0.2\n"
        "parallel_deg = 0.05\n"
    )
    assert _settings(user).check_thresholds() == CheckThresholds(
        epsilon_mm=0.02,
        text_clearance_mm=1.0,
        line_clearance_mm=0.3,
        edge_clearance_mm=0.4,
        font_metric_margin=0.2,
        parallel_deg=0.05,
    )
    assert _settings().check_thresholds() == CheckThresholds()


def test_settings_are_frozen_and_complete() -> None:
    settings = _settings()
    assert "local_app_data" in asdict(settings)
    try:
        settings.read_timeout_s = 1  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]
    except AttributeError:
        return
    raise AssertionError("Settings must be frozen")


def test_part_template_setting() -> None:
    assert _settings().part_template == ""

    user = _user(
        'config_version = "1.0"\n[part]\ntemplate = "C:\\\\Templates\\\\does_not_exist.prtdot"\n'
    )
    assert _settings(user).part_template == "C:\\Templates\\does_not_exist.prtdot"

    project = _project('config_version = "1.0"\n[part]\ntemplate = "D:\\\\Evil\\\\part.prtdot"\n')
    env = parse_env_layer({"SWMCP_PART__TEMPLATE": '"E:\\\\Evil\\\\part.prtdot"'})
    merged = _settings(user, project, env)
    assert merged.part_template == "C:\\Templates\\does_not_exist.prtdot"
    joined = "\n".join(merged.warnings)
    assert "part.template" in joined
    assert "D:" not in joined
    assert "E:" not in joined
    assert len(merged.warnings) == 2  # noqa: PLR2004

    for bad in (
        "relative\\part.prtdot",
        "C:\\Templates\\part.sldprt",
        "~\\part.prtdot",
        "%APPDATA%\\part.prtdot",
        "\\\\?\\C:\\Templates\\part.prtdot",
    ):
        escaped = bad.replace("\\", "\\\\")
        err = _error(_user(f'config_version = "1.0"\n[part]\ntemplate = "{escaped}"\n'))
        assert err.code == "CONFIG_INVALID"
        assert err.key == "part.template"
