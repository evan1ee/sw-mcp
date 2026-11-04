"""Path policy (spec 12.5): one pure function over the FileSystem port. No environment reads."""

import hashlib
import ntpath
import re
from dataclasses import dataclass
from typing import Final, Literal

from cad_ir.core.json_types import JsonValue

from cad_application.config import Settings
from cad_application.ports import FileSystem

_DEVICE_PREFIXES: Final = ("\\\\?\\", "\\\\.\\")
# 12.5: %NAME%, $env:, ${ and $( are references; any other "$" is an ordinary character.
_ENV_REFERENCE: Final = re.compile(r"%[^%\\]+%|\$env:|\$\{|\$\(", re.IGNORECASE)
_SETTING: Final = "access.allowed_roots"
_STORE_FOLDER: Final = ".cad"


@dataclass(frozen=True, slots=True)
class ToolError:
    """An error a tool returns (ADR-037); ``details`` never holds file contents or env values."""

    code: str
    message: str
    details: JsonValue = None


@dataclass(frozen=True, slots=True)
class Authorized:
    path: str
    root: str
    project_root: str
    store_dir: str
    in_vault: bool


def _denied(reason: str, message: str) -> ToolError:
    return ToolError("AUTH_PATH_DENIED", message, {"reason": reason})


def _syntax_error(path: str) -> ToolError | None:
    slashed = path.replace("/", "\\")
    if slashed.startswith(_DEVICE_PREFIXES):
        return _denied("device_prefix", "Device and extended-length path prefixes are not allowed.")
    if slashed.startswith("~") or _ENV_REFERENCE.search(path):
        return _denied(
            "home_or_env",
            "The path must be absolute; '~' and environment variables are not expanded.",
        )
    drive, rest = ntpath.splitdrive(slashed)
    if not drive or not rest.startswith("\\"):
        return _denied("not_absolute", "The path must be an absolute Windows path.")
    if ":" in rest:
        return _denied("stream", "A ':' after the drive would name an alternate data stream.")
    return None


def _normalised(fs: FileSystem, path: str) -> str:
    """Links and junctions followed; a path with a missing parent is only normalised."""
    try:
        return fs.resolve(path)
    except FileNotFoundError:
        return ntpath.normpath(path)


def _key(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path)).rstrip("\\")


def _within(path: str, root: str) -> bool:
    return _key(path) == _key(root) or _key(path).startswith(_key(root) + "\\")


def _is_unc(path: str) -> bool:
    return ntpath.splitdrive(path)[0].startswith("\\\\")


def _matching_root(path: str, roots: tuple[str, ...]) -> str | None:
    matches = [root for root in roots if _within(path, root)]
    return max(matches, key=lambda r: len(_key(r)), default=None)


def _project_root(fs: FileSystem, directory: str, root: str) -> str:
    """The nearest ancestor, up to ``root``, that holds a store; else ``root``."""
    current = directory
    while _within(current, root):
        found = fs.stat(ntpath.join(current, _STORE_FOLDER))
        if found is not None and found.is_dir:
            return current
        if _key(current) == _key(root):
            break
        parent = ntpath.dirname(current)
        if parent == current:
            break
        current = parent
    return root


def _store_dir(project_root: str, in_vault: bool, local_app_data: str) -> str:
    if not in_vault:
        return ntpath.join(project_root, _STORE_FOLDER)
    digest = hashlib.sha256(_key(project_root).encode("utf-8")).hexdigest()
    return ntpath.join(local_app_data, "sw-mcp", "stores", digest)


def _locate(path: str, settings: Settings, fs: FileSystem) -> tuple[str, str] | ToolError:
    """Steps 1-4 of 12.5: the normalised path and the allowed root it lies below."""
    if (error := _syntax_error(path)) is not None:
        return error
    if not settings.allowed_roots:
        return _denied(
            "no_roots", f"No folder is allowed: set {_SETTING} in the user configuration."
        )
    resolved = _normalised(fs, path)
    roots = tuple(_normalised(fs, root) for root in settings.allowed_roots)
    if _is_unc(resolved) and not any(_is_unc(root) for root in roots):
        return _denied("unc_not_allowed", "UNC paths need an allowed root that is a UNC path.")
    root = _matching_root(resolved, roots)
    if root is None:
        return _denied("outside_roots", f"The path is outside every folder in {_SETTING}.")
    return resolved, root


def _check_target(
    resolved: str, fs: FileSystem, expect: Literal["file", "dir"], suffix: str | None
) -> ToolError | None:
    """After authorization: the suffix, then that the target exists and is the right kind."""
    if suffix is not None and ntpath.splitext(resolved)[1].lower() != suffix.lower():
        return ToolError(
            "IR_SCHEMA_INVALID",
            f"The path must end with {suffix} (any case).",
            {"reason": "suffix"},
        )
    found = fs.stat(resolved)
    if found is None or found.is_dir != (expect == "dir"):
        what = "a folder" if expect == "dir" else "a file"
        return ToolError("FILE_NOT_FOUND", f"The path does not exist or is not {what}.", None)
    return None


def authorize(
    path: str,
    settings: Settings,
    fs: FileSystem,
    *,
    expect: Literal["file", "dir"] = "file",
    suffix: str | None = None,
) -> Authorized | ToolError:
    """Check ``path`` in the order of 12.5, then locate its project and store."""
    located = _locate(path, settings, fs)
    if isinstance(located, ToolError):
        return located
    resolved, root = located
    if (error := _check_target(resolved, fs, expect, suffix)) is not None:
        return error
    directory = resolved if expect == "dir" else ntpath.dirname(resolved)
    project = _project_root(fs, directory, root)
    in_vault = any(_within(project, _normalised(fs, v)) for v in settings.pdm_vault_roots)
    if in_vault and not settings.local_app_data:
        return ToolError("CONFIG_INVALID", "The local application data folder is unknown.", None)
    store_dir = _store_dir(project, in_vault, settings.local_app_data)
    if not in_vault and not _within(_normalised(fs, store_dir), root):
        return _denied("store_outside_roots", "The project store resolves outside its root.")
    return Authorized(
        path=resolved,
        root=root,
        project_root=project,
        store_dir=store_dir,
        in_vault=in_vault,
    )
