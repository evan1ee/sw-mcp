"""Parsing, validating and merging configuration layers (spec 13.3.1, 13.3.2). No I/O."""

import re
import tomllib
from collections.abc import Mapping, Sequence
from typing import Final, cast

from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema

from cad_application.config.settings import ConfigError, Layer, LayerSource, Settings

CONFIG_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/config/v1.json"
ENV_PREFIX: Final = "SWMCP_"
_CONFIG_VERSION: Final = "1.0"
# Security keys come from the user file only (13.3.1): a section name drops the whole section.
_SECURITY_KEYS: Final = ("access", "solidworks.session", "drawing.standard_dir")
_LINE = re.compile(r"line (\d+)")
_UNEXPECTED = re.compile(r"'([^']+)'")

type Tree = dict[str, JsonValue]


def lines_of(error: tomllib.TOMLDecodeError) -> int | None:
    """The line of a TOML syntax error, from its message."""
    found = _LINE.search(str(error))
    return int(found.group(1)) if found else None


def _jsonable(value: object) -> JsonValue:
    if isinstance(value, dict):
        members = cast("dict[str, object]", value)
        return {k: _jsonable(v) for k, v in members.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in cast("list[object]", value)]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)  # a TOML date or time: not a setting, kept as text so validation rejects it


def parse_toml_layer(text: str, *, source: LayerSource, origin: str) -> Layer | ConfigError:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return ConfigError(origin, None, lines_of(error), "TOML syntax error")
    values = cast("Tree", _jsonable(parsed))
    return Layer(source, origin, values)


def _env_value(raw: str) -> JsonValue:
    try:
        parsed = tomllib.loads(f"v = {raw}")["v"]
    except tomllib.TOMLDecodeError:
        return raw
    return _jsonable(parsed)


def parse_env_layer(environ: Mapping[str, str]) -> Layer:
    """Only ``SWMCP_<SECTION>__<KEY>`` variables; values are TOML values, else strings."""
    values: Tree = {}
    for name in sorted(environ):
        if not name.startswith(ENV_PREFIX) or len(name) == len(ENV_PREFIX):
            continue
        path = name[len(ENV_PREFIX) :].lower().split("__")
        node = values
        for part in path[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[path[-1]] = _env_value(environ[name])
    return Layer("env", "environment", values)


def _dotted(tree: Mapping[str, JsonValue], prefix: str = "") -> list[str]:
    keys: list[str] = []
    for name, value in tree.items():
        path = f"{prefix}{name}"
        keys.append(path)
        if isinstance(value, dict):
            keys += _dotted(value, path + ".")
    return keys


def _security_paths(values: Tree) -> list[tuple[str, ...]]:
    """Every security key present, as a path; ``access`` expands to its own keys."""
    found: list[tuple[str, ...]] = []
    access = values.get("access")
    if isinstance(access, dict):
        found += [("access", name) for name in access]
    for key in _SECURITY_KEYS[1:]:
        section, leaf = key.split(".")
        node = values.get(section)
        if isinstance(node, dict) and leaf in node:
            found.append((section, leaf))
    return found


def _drop_security(layer: Layer) -> tuple[Layer, list[str]]:
    """Remove security keys from a project or environment layer; warn by key, never by value."""
    if layer.source not in ("project", "env"):
        return layer, []
    values = cast("Tree", _jsonable(dict(layer.values)))
    warnings: list[str] = []
    for section, leaf in _security_paths(values):
        node = values[section]
        assert isinstance(node, dict)
        del node[leaf]
        warnings.append(f"{layer.origin}: ignored security key {section}.{leaf} (user file only)")
    if isinstance(values.get("access"), dict) and not values["access"]:
        del values["access"]
    return Layer(layer.source, layer.origin, values), warnings


def _variable(key: str) -> str:
    return ENV_PREFIX + key.replace(".", "__").upper()


def _describe(pointer: str, message: str, expected: Sequence[str]) -> tuple[str | None, str]:
    """A key and a message without any user-supplied value in it (G3)."""
    base = ".".join(p for p in pointer.split("/") if p)
    if "was unexpected" in message or "were unexpected" in message:
        name = _UNEXPECTED.search(message)
        key = ".".join(p for p in (base, name.group(1) if name else "") if p)
        return key, f"unknown key {key}"
    if "is a required property" in message:
        name = _UNEXPECTED.search(message)
        key = ".".join(p for p in (base, name.group(1) if name else "") if p)
        return key, f"missing required key {key}"
    key = base or None
    if "is not of type" in message:
        return key, f"wrong type for {key}: expected {', '.join(expected)}"
    shown = f"; expected {', '.join(expected)}" if expected else ""
    return key, f"invalid value for {key}{shown}"


def _validate(layer: Layer) -> ConfigError | None:
    document = dict(layer.values)
    if layer.source == "env":
        document["config_version"] = _CONFIG_VERSION
    issues = validate_against_schema(document, CONFIG_SCHEMA_ID)
    if not issues:
        return None
    first = issues[0]
    key, message = _describe(first.pointer, first.message, first.expected or ())
    origin = layer.origin
    if layer.source == "env" and key is not None:
        origin = _variable(key)
    return ConfigError(origin, key, None, message)


def _merge_into(base: Tree, top: Mapping[str, JsonValue]) -> Tree:
    out: Tree = dict(base)
    for name, value in top.items():
        current = out.get(name)
        if isinstance(value, dict) and isinstance(current, dict):
            out[name] = _merge_into(current, value)
        else:
            out[name] = value
    return out


def _get(tree: Tree, *path: str) -> JsonValue:
    node: JsonValue = tree
    for part in path:
        assert isinstance(node, dict)
        node = node[part]
    return node


def _ints(tree: Tree, *path: str) -> int:
    value = _get(tree, *path)
    assert isinstance(value, int)
    return value


def _num(tree: Tree, *path: str) -> float:
    value = _get(tree, *path)
    assert isinstance(value, int | float)
    return float(value)


def _text(tree: Tree, *path: str) -> str:
    value = _get(tree, *path)
    assert isinstance(value, str)
    return value


def _texts(tree: Tree, *path: str) -> tuple[str, ...]:
    value = _get(tree, *path)
    assert isinstance(value, list)
    return tuple(str(item) for item in value)


DEFAULTS: Final[Tree] = {
    "access": {"allowed_roots": [], "pdm_vault_roots": []},
    "mcp": {"toolsets": ["core", "drawing"]},
    "core": {"idle_shutdown_min": 30, "job_retention_days": 7},
    "solidworks": {
        "session": "auto",
        "command_timeout_s": 120,
        "read_timeout_s": 30,
        "ui_blocked_s": 30,
        "heartbeat_s": 10,
    },
    "drawing": {
        "job_timeout_min": 10,
        "relayout_max_iterations": 8,
        "pin_threshold_mm": 0.5,
        "standard_dir": "standards\\iso",
        "check": {
            "epsilon_mm": 0.01,
            "text_clearance_mm": 0.5,
            "line_clearance_mm": 0.25,
            "edge_clearance_mm": 0.25,
            "font_metric_margin": 0.1,
            "parallel_deg": 0.01,
        },
    },
    "store": {"snapshot_keep": 10, "backup_keep": 5},
    "logging": {"level": "info", "retention_days": 14},
}


def _settings_of(tree: Tree, warnings: tuple[str, ...]) -> Settings:
    session = _get(tree, "solidworks", "session")
    assert isinstance(session, str | int)
    return Settings(
        allowed_roots=_texts(tree, "access", "allowed_roots"),
        pdm_vault_roots=_texts(tree, "access", "pdm_vault_roots"),
        toolsets=_texts(tree, "mcp", "toolsets"),
        idle_shutdown_min=_ints(tree, "core", "idle_shutdown_min"),
        job_retention_days=_ints(tree, "core", "job_retention_days"),
        solidworks_session=session,
        command_timeout_s=_ints(tree, "solidworks", "command_timeout_s"),
        read_timeout_s=_ints(tree, "solidworks", "read_timeout_s"),
        ui_blocked_s=_ints(tree, "solidworks", "ui_blocked_s"),
        heartbeat_s=_ints(tree, "solidworks", "heartbeat_s"),
        job_timeout_min=_ints(tree, "drawing", "job_timeout_min"),
        relayout_max_iterations=_ints(tree, "drawing", "relayout_max_iterations"),
        pin_threshold_mm=_num(tree, "drawing", "pin_threshold_mm"),
        epsilon_mm=_num(tree, "drawing", "check", "epsilon_mm"),
        text_clearance_mm=_num(tree, "drawing", "check", "text_clearance_mm"),
        line_clearance_mm=_num(tree, "drawing", "check", "line_clearance_mm"),
        edge_clearance_mm=_num(tree, "drawing", "check", "edge_clearance_mm"),
        font_metric_margin=_num(tree, "drawing", "check", "font_metric_margin"),
        parallel_deg=_num(tree, "drawing", "check", "parallel_deg"),
        standard_dir=_text(tree, "drawing", "standard_dir"),
        snapshot_keep=_ints(tree, "store", "snapshot_keep"),
        backup_keep=_ints(tree, "store", "backup_keep"),
        logging_level=_text(tree, "logging", "level"),
        logging_retention_days=_ints(tree, "logging", "retention_days"),
        part_template=_text(tree, "part", "template")
        if "part" in tree and isinstance(tree["part"], dict) and "template" in tree["part"]
        else "",
        warnings=warnings,
    )


def merge_settings(layers: Sequence[Layer]) -> Settings | ConfigError:
    """Merge ``layers`` (lowest precedence first) over the built-in defaults, key by key."""
    merged: Tree = cast("Tree", _jsonable(DEFAULTS))
    warnings: list[str] = []
    for layer in layers:
        if layer.source == "defaults":
            merged = _merge_into(merged, layer.values)
            continue
        cleaned, dropped = _drop_security(layer)
        warnings += dropped
        if (error := _validate(cleaned)) is not None:
            return error
        body = {k: v for k, v in cleaned.values.items() if k != "config_version"}
        merged = _merge_into(merged, body)
    return _settings_of(merged, tuple(warnings))
