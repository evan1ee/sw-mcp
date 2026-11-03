"""Identifier grammars (spec 3.4.1). Patterns are unanchored; match with ``re.fullmatch``."""

import re
from typing import Final, Literal, TypeGuard

type ModuleKey = Literal["part", "assembly", "design_intent", "drawing_intent", "drawing_layout"]

MODULE_KEYS: Final[tuple[ModuleKey, ...]] = (
    "part",
    "assembly",
    "design_intent",
    "drawing_intent",
    "drawing_layout",
)

DOCUMENT_ID_PATTERN: Final = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
ITEM_ID_PATTERN: Final = r"[a-z][a-z0-9_]{0,63}"
DATUM_LABEL_PATTERN: Final = r"[A-HJ-NPR-Z]{1,2}"
REVISION_PATTERN: Final = r"[1-9][0-9]*"

_DOCUMENT_ID_RE: Final = re.compile(DOCUMENT_ID_PATTERN)
_ITEM_ID_RE: Final = re.compile(ITEM_ID_PATTERN)
_DATUM_LABEL_RE: Final = re.compile(DATUM_LABEL_PATTERN)


def is_module_key(s: str) -> TypeGuard[ModuleKey]:
    return s in MODULE_KEYS


def is_document_id(s: str) -> bool:
    return _DOCUMENT_ID_RE.fullmatch(s) is not None


def is_item_id(s: str) -> bool:
    return _ITEM_ID_RE.fullmatch(s) is not None


def is_datum_label(s: str) -> bool:
    return _DATUM_LABEL_RE.fullmatch(s) is not None
