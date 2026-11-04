"""Drawing Geometry Snapshot as frozen dataclasses (spec 11.5.1 Encoding).

``parse_snapshot`` validates against the schema first; unknown fields are ignored (ADR-042).
Every number is rounded to its quantum (3.4.3) by the kind the schema gives it (``x-quantity``:
points, radii and text heights are lengths, arc ends are angles, the view scale is a ratio), so
the checks run on the snapshot as stored. The input document is never modified.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

from cad_ir.core import (
    IssueReport,
    JsonValue,
    ValidationIssue,
    build_report,
    json_pointer,
    quantize,
    validate_against_schema,
)
from cad_ir.generated import ErrorCode

from cad_drawing.checks.geometry2d import Vec

SNAPSHOT_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"

type TextMethod = Literal["display_data", "font_metrics"]
type AnnotationKind = Literal[
    "dimension",
    "callout",
    "note",
    "gdt",
    "datum",
    "surface_finish",
    "center_mark",
    "centerline",
    "balloon",
]
type EdgeKind = Literal["visible", "silhouette", "hidden", "centerline", "center_mark"]
type RebuildErrorKind = Literal["dangling", "annotation_error", "rebuild_error"]
type ReopenState = Literal["verified", "failed", "not_checked"]


@dataclass(frozen=True, slots=True)
class PolylineCurve:
    points: tuple[Vec, ...]


@dataclass(frozen=True, slots=True)
class ArcCurve:
    """Counter-clockwise from ``start_deg`` to ``end_deg``."""

    center: Vec
    radius: float
    start_deg: float
    end_deg: float


type Curve = PolylineCurve | ArcCurve


@dataclass(frozen=True, slots=True)
class Rect:
    min: Vec
    max: Vec


@dataclass(frozen=True, slots=True)
class TextBox:
    corners: tuple[Vec, Vec, Vec, Vec]
    height_mm: float
    method: TextMethod
    text: str


@dataclass(frozen=True, slots=True)
class ExtensionLine:
    line: tuple[Vec, ...]
    entity: str


@dataclass(frozen=True, slots=True)
class Arrowhead:
    polygon: tuple[Vec, ...]


@dataclass(frozen=True, slots=True)
class Annotation:
    key: str
    kind: AnnotationKind
    native_id: str
    tag: str | None
    view: str | None
    attachments: tuple[str, ...]
    dimension_lines: tuple[Curve, ...]
    extension_lines: tuple[ExtensionLine, ...]
    arrowheads: tuple[Arrowhead, ...]
    leaders: tuple[tuple[Vec, ...], ...]
    text_boxes: tuple[TextBox, ...]
    parameters: tuple[str, ...] | None = None
    parenthesized: bool | None = None


@dataclass(frozen=True, slots=True)
class Edge:
    curve: Curve
    kind: EdgeKind


@dataclass(frozen=True, slots=True)
class View:
    key: str
    native_id: str
    scale: float
    outline: Rect
    edges: tuple[Edge, ...]


@dataclass(frozen=True, slots=True)
class RevisionTable:
    entries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Sheet:
    key: str
    index: int
    native_id: str
    size_mm: Vec
    border: Rect
    title_block: tuple[Rect, ...]
    views: tuple[View, ...]
    annotations: tuple[Annotation, ...]
    sheet_format: str | None = None
    title_block_fields: tuple[tuple[str, str], ...] | None = None
    revision_table: RevisionTable | None = None


@dataclass(frozen=True, slots=True)
class RebuildError:
    kind: RebuildErrorKind
    sheet: str | None
    annotation: str | None
    message: str


@dataclass(frozen=True, slots=True)
class AnnotationRef:
    sheet: str
    annotation: str


@dataclass(frozen=True, slots=True)
class Rebuild:
    completed: bool
    errors: tuple[RebuildError, ...]
    silhouette_attachments: tuple[AnnotationRef, ...]
    reopen: ReopenState


@dataclass(frozen=True, slots=True)
class Snapshot:
    schema_version: str
    document: str
    revision: int | None
    solidworks_version: str
    service_pack: str
    captured_at: str
    sheets: tuple[Sheet, ...]
    rebuild: Rebuild | None = None


# The helpers below read a document that already passed schema validation, so a type mismatch
# is a programming error, not a user error.
type _Obj = dict[str, JsonValue]


def _obj(value: JsonValue) -> _Obj:
    if not isinstance(value, dict):
        raise TypeError(f"expected an object, got {type(value).__name__}")
    return value


def _arr(value: JsonValue | None) -> list[JsonValue]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"expected an array, got {type(value).__name__}")
    return value


def _num(value: JsonValue | None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    return float(value)


def _length(value: JsonValue | None) -> float:
    return float(quantize(_num(value), "length"))


def _angle(value: JsonValue | None) -> float:
    return float(quantize(_num(value), "angle"))


def _ratio(value: JsonValue | None) -> float:
    return float(quantize(_num(value), "ratio"))


def _str(value: JsonValue | None) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {type(value).__name__}")
    return value


def _opt_str(value: JsonValue | None) -> str | None:
    return None if value is None else _str(value)


def _opt_bool(value: JsonValue | None) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"expected a boolean, got {type(value).__name__}")
    return value


def _vec(value: JsonValue) -> Vec:
    x, y = _arr(value)
    return (_length(x), _length(y))


def _vecs(value: JsonValue | None) -> tuple[Vec, ...]:
    return tuple(_vec(v) for v in _arr(value))


def _rect(value: JsonValue) -> Rect:
    o = _obj(value)
    return Rect(_vec(o["min"]), _vec(o["max"]))


def _curve(value: JsonValue) -> Curve:
    o = _obj(value)
    if "polyline" in o:
        return PolylineCurve(_vecs(o["polyline"]))
    arc = _obj(o["arc"])
    return ArcCurve(
        _vec(arc["center"]),
        _length(arc["radius"]),
        _angle(arc["start_deg"]),
        _angle(arc["end_deg"]),
    )


def _text_box(value: JsonValue) -> TextBox:
    o = _obj(value)
    a, b, c, d = _vecs(o["corners"])
    return TextBox(
        (a, b, c, d),
        _length(o["height_mm"]),
        cast(TextMethod, _str(o["method"])),
        _str(o["text"]),
    )


def _annotation(key: str, value: JsonValue) -> Annotation:
    o = _obj(value)
    extension_lines = tuple(
        ExtensionLine(_vecs(_obj(e)["line"]), _str(_obj(e)["entity"]))
        for e in _arr(o.get("extension_lines"))
    )
    return Annotation(
        key=key,
        kind=cast(AnnotationKind, _str(o["kind"])),
        native_id=_str(o["native_id"]),
        tag=_opt_str(o.get("tag")),
        view=_opt_str(o.get("view")),
        attachments=tuple(sorted(_str(a) for a in _arr(o.get("attachments")))),
        dimension_lines=tuple(_curve(c) for c in _arr(o.get("dimension_lines"))),
        extension_lines=extension_lines,
        arrowheads=tuple(Arrowhead(_vecs(_obj(a)["polygon"])) for a in _arr(o.get("arrowheads"))),
        leaders=tuple(_vecs(leader) for leader in _arr(o.get("leaders"))),
        text_boxes=tuple(_text_box(t) for t in _arr(o.get("text_boxes"))),
        parameters=_parameters(o.get("parameters")),
        parenthesized=_opt_bool(o.get("parenthesized")),
    )


def _parameters(value: JsonValue | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(sorted(_str(p) for p in _arr(value)))


def _view(key: str, value: JsonValue) -> View:
    o = _obj(value)
    edges = tuple(
        Edge(_curve(_obj(e)["curve"]), cast(EdgeKind, _str(_obj(e)["kind"])))
        for e in _arr(o["edges"])
    )
    return View(key, _str(o["native_id"]), _ratio(o["scale"]), _rect(o["outline"]), edges)


def _sheet(key: str, value: JsonValue) -> Sheet:
    o = _obj(value)
    index = o["index"]
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("sheet index must be an integer")
    views = _obj(o["views"])
    annotations = _obj(o["annotations"])
    return Sheet(
        key=key,
        index=index,
        native_id=_str(o["native_id"]),
        size_mm=_vec(o["size_mm"]),
        border=_rect(o["border"]),
        title_block=tuple(_rect(r) for r in _arr(o["title_block"])),
        views=tuple(_view(k, views[k]) for k in sorted(views)),
        annotations=tuple(_annotation(k, annotations[k]) for k in sorted(annotations)),
        sheet_format=_opt_str(o.get("sheet_format")),
        title_block_fields=_title_fields(o.get("title_block_fields")),
        revision_table=_revision_table(o.get("revision_table")),
    )


def _title_fields(value: JsonValue | None) -> tuple[tuple[str, str], ...] | None:
    if value is None:
        return None
    fields = _obj(value)
    return tuple((name, _str(fields[name])) for name in sorted(fields))


def _revision_table(value: JsonValue | None) -> RevisionTable | None:
    if value is None:
        return None
    return RevisionTable(tuple(_str(e) for e in _arr(_obj(value)["entries"])))


def _rebuild(value: JsonValue | None) -> Rebuild | None:
    if value is None:
        return None
    o = _obj(value)
    errors = tuple(
        RebuildError(
            cast(RebuildErrorKind, _str(_obj(e)["kind"])),
            _opt_str(_obj(e)["sheet"]),
            _opt_str(_obj(e)["annotation"]),
            _str(_obj(e)["message"]),
        )
        for e in _arr(o["errors"])
    )
    refs = tuple(
        AnnotationRef(_str(_obj(r)["sheet"]), _str(_obj(r)["annotation"]))
        for r in _arr(o["silhouette_attachments"])
    )
    completed = o["completed"]
    if not isinstance(completed, bool):
        raise TypeError("rebuild.completed must be a boolean")
    return Rebuild(completed, errors, refs, cast(ReopenState, _str(o["reopen"])))


def _inverted(rect: Rect) -> bool:
    return rect.min[0] > rect.max[0] or rect.min[1] > rect.max[1]


def _rect_issues(sheet: Sheet) -> list[ValidationIssue]:
    """JSON Schema cannot compare two fields, so ``min <= max`` is checked here."""
    rects: list[tuple[tuple[str | int, ...], Rect]] = [
        (("sheets", sheet.key, "border"), sheet.border)
    ]
    rects.extend(
        (("sheets", sheet.key, "title_block", i), r) for i, r in enumerate(sheet.title_block)
    )
    rects.extend((("sheets", sheet.key, "views", v.key, "outline"), v.outline) for v in sheet.views)
    return [
        ValidationIssue(
            code=ErrorCode.IR_RULE_VIOLATED,
            pointer=json_pointer(*tokens),
            message="rectangle min must not exceed max on either axis",
        )
        for tokens, rect in rects
        if _inverted(rect)
    ]


def _unknown(pointer: tuple[str | int, ...], what: str) -> ValidationIssue:
    return ValidationIssue(
        code=ErrorCode.IR_RULE_VIOLATED,
        pointer=json_pointer(*pointer),
        message=what,
    )


def _ref_issues(
    base: tuple[str | int, ...],
    sheet: str | None,
    annotation: str | None,
    known: Mapping[str, frozenset[str]],
) -> list[ValidationIssue]:
    if sheet is not None and sheet not in known:
        return [_unknown((*base, "sheet"), "sheet names no sheet in the snapshot")]
    if annotation is None:
        return []
    if sheet is None:
        return [_unknown((*base, "annotation"), "an annotation reference needs its sheet")]
    if annotation not in known[sheet]:
        return [_unknown((*base, "annotation"), "annotation names no annotation on the sheet")]
    return []


def _rebuild_issues(rebuild: Rebuild | None, sheets: Sequence[Sheet]) -> list[ValidationIssue]:
    """References in ``rebuild`` must name items of the snapshot."""
    if rebuild is None:
        return []
    known = {s.key: frozenset(a.key for a in s.annotations) for s in sheets}
    issues: list[ValidationIssue] = []
    for i, error in enumerate(rebuild.errors):
        base = ("rebuild", "errors", i)
        issues.extend(_ref_issues(base, error.sheet, error.annotation, known))
    for i, ref in enumerate(rebuild.silhouette_attachments):
        base = ("rebuild", "silhouette_attachments", i)
        issues.extend(_ref_issues(base, ref.sheet, ref.annotation, known))
    return issues


def parse_snapshot(doc: JsonValue) -> Snapshot | IssueReport:
    """Validate ``doc`` against the snapshot schema, then build the quantized model."""
    issues = validate_against_schema(doc, SNAPSHOT_SCHEMA_ID)
    if issues:
        return build_report(issues)
    root = _obj(doc)
    drawing = _obj(root["drawing"])
    solidworks = _obj(root["solidworks"])
    revision = drawing.get("revision")
    sheets = _obj(root["sheets"])
    parsed = sorted((_sheet(k, sheets[k]) for k in sheets), key=lambda s: (s.index, s.key))
    rebuild = _rebuild(root.get("rebuild"))
    rule_issues = [issue for sheet in parsed for issue in _rect_issues(sheet)]
    rule_issues.extend(_rebuild_issues(rebuild, parsed))
    if rule_issues:
        return build_report(rule_issues)
    return Snapshot(
        schema_version=_str(root["schema_version"]),
        document=_str(drawing["document"]),
        revision=revision if isinstance(revision, int) else None,
        solidworks_version=_str(solidworks["version"]),
        service_pack=_str(solidworks["service_pack"]),
        captured_at=_str(root["captured_at"]),
        sheets=tuple(parsed),
        rebuild=rebuild,
    )
