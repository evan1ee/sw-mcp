"""Title-block mappings from ``<standard_dir>\\title-blocks\\*.toml`` (spec 13.3.4)."""

import ntpath
import tomllib
from collections.abc import Mapping
from typing import Final, cast

from cad_drawing.checks import TitleBlockMapping
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema

from cad_application.config.merge import _describe, _jsonable, lines_of  # pyright: ignore[reportPrivateUsage]
from cad_application.config.settings import ConfigError
from cad_application.ports import FileSystem

TITLE_BLOCK_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/config/title-block/v1.json"
FOLDER: Final = "title-blocks"


def _mapping(origin: str, text: str) -> TitleBlockMapping | ConfigError:
    try:
        parsed = _jsonable(tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        return ConfigError(origin, None, lines_of(error), "TOML syntax error")
    issues = validate_against_schema(parsed, TITLE_BLOCK_SCHEMA_ID)
    if issues:
        key, message = _describe(issues[0].pointer, issues[0].message, issues[0].expected or ())
        return ConfigError(origin, key, None, message)
    assert isinstance(parsed, dict)
    fields = cast("Mapping[str, Mapping[str, JsonValue]]", parsed["fields"])
    return TitleBlockMapping(
        template=cast("str", parsed["template"]),
        required=tuple(name for name, field in fields.items() if field.get("required") is True),
        revision_table=parsed.get("revision_table") is True,
    )


def load_title_block_mappings(
    fs: FileSystem, standard_dir: str
) -> Mapping[str, TitleBlockMapping] | ConfigError:
    """Mappings keyed by template. A missing folder gives ``{}``; nothing else is read."""
    folder = ntpath.join(standard_dir, FOLDER)
    stat = fs.stat(folder)
    if stat is None or not stat.is_dir:
        return {}
    mappings: dict[str, TitleBlockMapping] = {}
    for name in fs.list_dir(folder):
        if not name.lower().endswith(".toml"):
            continue
        origin = ntpath.join(folder, name)
        try:
            text = fs.read_bytes(origin).decode("utf-8")
        except UnicodeDecodeError:
            return ConfigError(origin, None, None, "file is not UTF-8 text")
        mapping = _mapping(origin, text)
        if isinstance(mapping, ConfigError):
            return mapping
        if mapping.template in mappings:
            return ConfigError(origin, "template", None, "duplicate template mapping")
        mappings[mapping.template] = mapping
    return mappings
