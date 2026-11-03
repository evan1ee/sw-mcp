"""Typed reference values and parsers (spec 3.4.2).

A reference's kind is fixed by the field that holds it; each parser accepts exactly one form
and never normalizes its input.
"""

import re
from dataclasses import dataclass
from typing import Final, Literal, cast

from cad_ir.core.ids import (
    DATUM_LABEL_PATTERN,
    DOCUMENT_ID_PATTERN,
    ITEM_ID_PATTERN,
    MODULE_KEYS,
    REVISION_PATTERN,
    ModuleKey,
)

_NAME_FULL: Final = re.compile(r"[^\x00-\x1f\x7f-\x9f\u2028\u2029]+")
_DOC_FORM: Final = "<module>:<document_id>[@<revision>]"
_ITEM_FORM: Final = "<module>:<document_id>[@<revision>]/<item_id>"
_LOCAL_FORM: Final = "<item_id>"
_INTENT_FORM: Final = "<kind>:<id>, kind is scheme, critical, gdt, datum or finish"
_PARAM_FORM: Final = "<feature_id>.<parameter>"
_GEOMETRY_FORM: Final = (
    "<feature_id>.<role> | geo:<reference_id> | plane:front | plane:top | plane:right"
    " | origin | datum:<label>"
)
_SWDIM_FORM: Final = "swdim:<full name>"

_MODULE_ALT: Final = "|".join(MODULE_KEYS)
_DOC_CORE: Final = (
    rf"(?P<module>{_MODULE_ALT}):(?P<id>{DOCUMENT_ID_PATTERN})(?:@(?P<rev>{REVISION_PATTERN}))?"
)

_DOC_RE: Final = re.compile(_DOC_CORE)
_ITEM_RE: Final = re.compile(rf"{_DOC_CORE}/(?P<item>{ITEM_ID_PATTERN})")
_LOCAL_RE: Final = re.compile(ITEM_ID_PATTERN)
_INTENT_ITEM_RE: Final = re.compile(
    rf"(?P<kind>scheme|critical|gdt|finish):(?P<id>{ITEM_ID_PATTERN})"
)
_INTENT_DATUM_RE: Final = re.compile(rf"datum:(?P<id>{DATUM_LABEL_PATTERN})")
_PARAM_RE: Final = re.compile(rf"(?P<feature>{ITEM_ID_PATTERN})\.(?P<name>{ITEM_ID_PATTERN})")
_STORED_GEO_RE: Final = re.compile(rf"geo:(?P<id>{ITEM_ID_PATTERN})")
_DATUM_GEO_RE: Final = re.compile(rf"datum:(?P<label>{DATUM_LABEL_PATTERN})")
_STANDARD_NAMES: Final = ("plane:front", "plane:top", "plane:right", "origin")
_SWDIM_RE: Final = re.compile(r"swdim:(?P<name>[^\x00-\x1f\x7f-\x9f\u2028\u2029]+)")


class ReferenceSyntaxError(ValueError):
    """A string does not have the form its field type requires."""

    def __init__(self, ref: str, expected: str) -> None:
        super().__init__(f"invalid reference {ref!r}: expected {expected}")
        self.ref = ref
        self.expected = expected


def _check(pattern: re.Pattern[str], value: object, what: str) -> None:
    """Raise ``ValueError`` unless ``value`` is a string matching ``pattern`` as a whole."""
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {what}: {value!r}")


_ITEM_ID_RE: Final = re.compile(ITEM_ID_PATTERN)
_DOCUMENT_ID_RE: Final = re.compile(DOCUMENT_ID_PATTERN)
_DATUM_LABEL_RE: Final = re.compile(DATUM_LABEL_PATTERN)
_INTENT_KINDS: Final = ("scheme", "critical", "gdt", "datum", "finish")


@dataclass(frozen=True, slots=True)
class DocumentRef:
    module: ModuleKey
    document_id: str
    revision: int | None = None

    def __post_init__(self) -> None:
        if self.module not in MODULE_KEYS:
            raise ValueError(f"invalid module key: {self.module!r}")
        _check(_DOCUMENT_ID_RE, self.document_id, "document ID")
        if self.revision is not None and (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)  # pyright: ignore[reportUnnecessaryIsInstance]
            or self.revision < 1
        ):
            raise ValueError(f"invalid revision: {self.revision!r}")

    def __str__(self) -> str:
        base = f"{self.module}:{self.document_id}"
        return base if self.revision is None else f"{base}@{self.revision}"


@dataclass(frozen=True, slots=True)
class ItemRef:
    document: DocumentRef
    item_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.document, DocumentRef):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"invalid document reference: {self.document!r}")
        _check(_ITEM_ID_RE, self.item_id, "item ID")

    def __str__(self) -> str:
        return f"{self.document}/{self.item_id}"


@dataclass(frozen=True, slots=True)
class LocalRef:
    item_id: str

    def __post_init__(self) -> None:
        _check(_ITEM_ID_RE, self.item_id, "item ID")

    def __str__(self) -> str:
        return self.item_id


type IntentKind = Literal["scheme", "critical", "gdt", "datum", "finish"]


@dataclass(frozen=True, slots=True)
class IntentItemRef:
    kind: IntentKind
    id: str

    def __post_init__(self) -> None:
        if self.kind not in _INTENT_KINDS:
            raise ValueError(f"invalid intent item kind: {self.kind!r}")
        if self.kind == "datum":
            _check(_DATUM_LABEL_RE, self.id, "datum label")
        else:
            _check(_ITEM_ID_RE, self.id, "item ID")

    def __str__(self) -> str:
        return f"{self.kind}:{self.id}"


@dataclass(frozen=True, slots=True)
class ParamRef:
    feature_id: str
    parameter: str

    def __post_init__(self) -> None:
        _check(_ITEM_ID_RE, self.feature_id, "feature ID")
        _check(_ITEM_ID_RE, self.parameter, "parameter name")

    def __str__(self) -> str:
        return f"{self.feature_id}.{self.parameter}"


@dataclass(frozen=True, slots=True)
class FeatureRoleRef:
    feature_id: str
    role: str

    def __post_init__(self) -> None:
        _check(_ITEM_ID_RE, self.feature_id, "feature ID")
        _check(_ITEM_ID_RE, self.role, "role name")

    def __str__(self) -> str:
        return f"{self.feature_id}.{self.role}"


@dataclass(frozen=True, slots=True)
class StoredGeometryRef:
    reference_id: str

    def __post_init__(self) -> None:
        _check(_ITEM_ID_RE, self.reference_id, "geometry reference ID")

    def __str__(self) -> str:
        return f"geo:{self.reference_id}"


type StandardGeometryName = Literal["plane:front", "plane:top", "plane:right", "origin"]


@dataclass(frozen=True, slots=True)
class StandardGeometryRef:
    name: StandardGeometryName

    def __post_init__(self) -> None:
        if self.name not in _STANDARD_NAMES:
            raise ValueError(f"invalid standard geometry name: {self.name!r}")

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class DatumGeometryRef:
    label: str

    def __post_init__(self) -> None:
        _check(_DATUM_LABEL_RE, self.label, "datum label")

    def __str__(self) -> str:
        return f"datum:{self.label}"


type GeometryRef = FeatureRoleRef | StoredGeometryRef | StandardGeometryRef | DatumGeometryRef


@dataclass(frozen=True, slots=True)
class SolidWorksDimRef:
    full_name: str

    def __post_init__(self) -> None:
        _check(_NAME_FULL, self.full_name, "SOLIDWORKS dimension name")

    def __str__(self) -> str:
        return f"swdim:{self.full_name}"


def _match(pattern: re.Pattern[str], s: str, expected: str) -> re.Match[str]:
    m = pattern.fullmatch(s)
    if m is None:
        raise ReferenceSyntaxError(s, expected)
    return m


def _document(m: re.Match[str]) -> DocumentRef:
    rev = m.group("rev")
    return DocumentRef(
        cast(ModuleKey, m.group("module")), m.group("id"), None if rev is None else int(rev)
    )


def parse_document_ref(s: str) -> DocumentRef:
    return _document(_match(_DOC_RE, s, _DOC_FORM))


def parse_item_ref(s: str) -> ItemRef:
    m = _match(_ITEM_RE, s, _ITEM_FORM)
    return ItemRef(_document(m), m.group("item"))


def parse_local_ref(s: str) -> LocalRef:
    _match(_LOCAL_RE, s, _LOCAL_FORM)
    return LocalRef(s)


def parse_intent_item_ref(s: str) -> IntentItemRef:
    m = _INTENT_ITEM_RE.fullmatch(s) or _INTENT_DATUM_RE.fullmatch(s)
    if m is None:
        raise ReferenceSyntaxError(s, _INTENT_FORM)
    kind = cast(IntentKind, "datum" if s.startswith("datum:") else m.group("kind"))
    return IntentItemRef(kind, m.group("id"))


def parse_param_ref(s: str) -> ParamRef:
    m = _match(_PARAM_RE, s, _PARAM_FORM)
    return ParamRef(m.group("feature"), m.group("name"))


def parse_geometry_ref(s: str) -> GeometryRef:
    if s in _STANDARD_NAMES:
        return StandardGeometryRef(s)
    if (m := _STORED_GEO_RE.fullmatch(s)) is not None:
        return StoredGeometryRef(m.group("id"))
    if (m := _DATUM_GEO_RE.fullmatch(s)) is not None:
        return DatumGeometryRef(m.group("label"))
    if (m := _PARAM_RE.fullmatch(s)) is not None:
        return FeatureRoleRef(m.group("feature"), m.group("name"))
    raise ReferenceSyntaxError(s, _GEOMETRY_FORM)


def parse_solidworks_dim_ref(s: str) -> SolidWorksDimRef:
    m = _match(_SWDIM_RE, s, _SWDIM_FORM)
    return SolidWorksDimRef(m.group("name"))
