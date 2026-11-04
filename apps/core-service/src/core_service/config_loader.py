"""Reads the user file, the environment and project files into ``Settings`` (spec 13.3).

``cad_application.config`` merges and validates; this module only reads. The user file is
``%APPDATA%\\sw-mcp\\config.toml``; a project file is ``<project>\\.cad\\config.toml``, read again
when its modification time or size changes. Layers, lowest first: defaults, user, project,
environment. A file may start with a UTF-8 byte order mark (Notepad writes one).
"""

import ntpath
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from cad_application.config import (
    ConfigError,
    Layer,
    Settings,
    merge_settings,
    parse_env_layer,
    parse_toml_layer,
)
from cad_application.config.settings import LayerSource
from cad_application.ports import FileSystem

_USER_FOLDER: Final = "sw-mcp"
_CONFIG_NAME: Final = "config.toml"
_PROJECT_FOLDER: Final = ".cad"


@dataclass(frozen=True, slots=True)
class CoreConfig:
    """The settings every tool call starts from, and the layers a project file is merged with."""

    settings: Settings
    user_layer: Layer | None
    env_layer: Layer
    install_root: str
    local_app_data: str

    @property
    def logs_dir(self) -> str:
        return ntpath.join(self.local_app_data, _USER_FOLDER, "logs")

    @property
    def known_stores_path(self) -> str:
        return ntpath.join(self.local_app_data, _USER_FOLDER, "known-stores.json")


def _finalize(settings: Settings, install_root: str, local_app_data: str) -> Settings:
    """Fill what the configuration cannot know: the installation and the local data folder."""
    standard = ntpath.normpath(ntpath.join(install_root, settings.standard_dir))
    return replace(settings, standard_dir=standard, local_app_data=local_app_data)


def _read_layer(fs: FileSystem, path: str, source: LayerSource) -> Layer | ConfigError:
    try:
        found = fs.stat(path)
        if found is None:
            return ConfigError(path, None, None, "the file does not exist")
        if found.is_dir:
            return ConfigError(path, None, None, "the path is a folder, not a file")
        data = fs.read_bytes(path)
    except (OSError, ValueError):
        return ConfigError(path, None, None, "the file cannot be read")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ConfigError(path, None, None, "the file is not UTF-8 text")
    return parse_toml_layer(text, source=source, origin=path)


def _merged(
    layers: Sequence[Layer | None], install_root: str, local_app_data: str
) -> Settings | ConfigError:
    merged = merge_settings([layer for layer in layers if layer is not None])
    if isinstance(merged, ConfigError):
        return merged
    return _finalize(merged, install_root, local_app_data)


def _local_app_data(environ: Mapping[str, str]) -> str | ConfigError:
    value = environ.get("LOCALAPPDATA", "")
    drive, rest = ntpath.splitdrive(value)
    if not drive or not rest.startswith("\\"):
        return ConfigError(
            "environment", "LOCALAPPDATA", None, "LOCALAPPDATA must be an absolute path"
        )
    return ntpath.normpath(value)


def _user_layer(fs: FileSystem, environ: Mapping[str, str]) -> Layer | ConfigError | None:
    appdata = environ.get("APPDATA")
    if not appdata:
        return None
    path = ntpath.join(appdata, _USER_FOLDER, _CONFIG_NAME)
    try:
        if fs.stat(path) is None:
            return None
    except (OSError, ValueError):
        return ConfigError(path, None, None, "the file cannot be read")
    return _read_layer(fs, path, "user")


def load_core_config(
    fs: FileSystem, environ: Mapping[str, str], install_root: str
) -> CoreConfig | ConfigError:
    """The core's configuration; an invalid user file or environment refuses start (13.3.2)."""
    local = _local_app_data(environ)
    if isinstance(local, ConfigError):
        return local
    user = _user_layer(fs, environ)
    if isinstance(user, ConfigError):
        return user
    env = parse_env_layer(environ)
    settings = _merged([user, env], install_root, local)
    if isinstance(settings, ConfigError):
        return settings
    return CoreConfig(settings, user, env, install_root, local)


class ProjectSettings:
    """``Settings`` for a project folder: the user and environment layers around its file."""

    def __init__(self, fs: FileSystem, config: CoreConfig) -> None:
        self._fs = fs
        self._config = config
        self._guard = threading.Lock()
        self._cache: dict[str, tuple[tuple[int, int], Settings | ConfigError]] = {}

    def __call__(self, project_root: str) -> Settings | ConfigError:
        path = ntpath.join(project_root, _PROJECT_FOLDER, _CONFIG_NAME)
        try:
            found = self._fs.stat(path)
        except (OSError, ValueError):
            return ConfigError(path, None, None, "the file cannot be read")
        if found is None:
            return self._config.settings
        key = (found.mtime_ns, found.size)
        name = ntpath.normcase(path)
        with self._guard:
            cached = self._cache.get(name)
            if cached is not None and cached[0] == key:
                return cached[1]
            result = self._load(path)
            self._cache[name] = (key, result)
            return result

    def _load(self, path: str) -> Settings | ConfigError:
        layer = _read_layer(self._fs, path, "project")
        if isinstance(layer, ConfigError):
            return layer
        c = self._config
        return _merged([c.user_layer, layer, c.env_layer], c.install_root, c.local_app_data)
