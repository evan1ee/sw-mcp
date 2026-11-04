"""Dataclass models for Drawing Layout IR (spec 11.11)."""

from dataclasses import dataclass, field
from typing import Any, Final

LAYOUT_SCHEMA_ID: Final[str] = "https://sw-mcp.invalid/schemas/drawing-layout/v0.json"


def _empty_modifiers() -> dict[str, Any]:
    return {}


def _empty_annotations() -> dict[str, "DrawingAnnotation"]:
    return {}


def _empty_tables() -> dict[str, dict[str, Any]]:
    return {}


def _empty_title_block() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class DrawingSheet:
    """Sheet definition in Drawing Layout IR."""

    size: str | None = None
    orientation: str | None = None
    scale: str | None = None
    sheet_format: str | None = None
    template: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        if self.size is not None:
            res["size"] = self.size
        if self.orientation is not None:
            res["orientation"] = self.orientation
        if self.scale is not None:
            res["scale"] = self.scale
        if self.sheet_format is not None:
            res["sheet_format"] = self.sheet_format
        if self.template is not None:
            res["template"] = self.template
        return res


@dataclass(frozen=True, slots=True)
class ViewDisplay:
    """View display parameters."""

    hidden_lines: bool = False
    tangent_edges: str = "removed"  # "removed", "phantom", "visible"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hidden_lines": self.hidden_lines,
            "tangent_edges": self.tangent_edges,
        }


@dataclass(frozen=True, slots=True)
class DrawingView:
    """View definition in Drawing Layout IR."""

    sheet: str
    type: str  # "base", "projected", "isometric", etc.
    position: tuple[float, float]  # (x, y) in sheet mm
    scale: str  # e.g. "1:1", "1:2"
    orientation: str = "front"
    configuration: str = "Default"
    parent: str | None = None
    display: ViewDisplay = field(default_factory=ViewDisplay)
    label: str | None = None
    modifiers: dict[str, Any] = field(default_factory=_empty_modifiers)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "sheet": self.sheet,
            "type": self.type,
            "orientation": self.orientation,
            "scale": self.scale,
            "position": [self.position[0], self.position[1]],
            "display": self.display.to_dict(),
        }
        if self.configuration != "Default":
            res["configuration"] = self.configuration
        if self.parent is not None:
            res["parent"] = self.parent
        if self.label is not None:
            res["label"] = self.label
        if self.modifiers:
            res["modifiers"] = self.modifiers
        return res


@dataclass(frozen=True, slots=True)
class DrawingAnnotation:
    """Annotation definition in Drawing Layout IR."""

    kind: str  # "dimension", "callout", "note", etc.
    view: str
    text_position: tuple[float, float]
    intent_ref: str | None = None
    tag: str | None = None
    native_id: str | None = None
    placed_by: str = "pipeline"  # "pipeline", "manual", "agent"
    pinned: bool = False
    side: str | None = None
    offset: float | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "kind": self.kind,
            "view": self.view,
            "text_position": [self.text_position[0], self.text_position[1]],
            "placed_by": self.placed_by,
            "pinned": self.pinned,
        }
        if self.intent_ref is not None:
            res["intent_ref"] = self.intent_ref
        if self.tag is not None:
            res["tag"] = self.tag
        if self.native_id is not None:
            res["native_id"] = self.native_id
        if self.side is not None:
            res["side"] = self.side
        if self.offset is not None:
            res["offset"] = self.offset
        return res


@dataclass(frozen=True, slots=True)
class DrawingLayout:
    """Root Drawing Layout IR document (spec 11.11)."""

    id: str
    schema_version: str
    units: str
    intent: str
    sheets: dict[str, DrawingSheet]
    views: dict[str, DrawingView]
    annotations: dict[str, DrawingAnnotation] = field(default_factory=_empty_annotations)
    revision: int | None = None
    part_path: str | None = None
    drafting_standard: str | None = None
    template: str | None = None
    tables: dict[str, dict[str, Any]] = field(default_factory=_empty_tables)
    title_block: dict[str, str] = field(default_factory=_empty_title_block)

    def to_dict(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "module": "drawing_layout",
            "id": self.id,
            "schema_version": self.schema_version,
            "units": self.units,
            "intent": self.intent,
            "sheets": {k: v.to_dict() for k, v in self.sheets.items()},
            "views": {k: v.to_dict() for k, v in self.views.items()},
        }
        if self.revision is not None:
            doc["revision"] = self.revision
        if self.part_path is not None:
            doc["part_path"] = self.part_path
        if self.drafting_standard is not None:
            doc["drafting_standard"] = self.drafting_standard
        if self.template is not None:
            doc["template"] = self.template
        if self.annotations:
            doc["annotations"] = {k: v.to_dict() for k, v in self.annotations.items()}
        if self.tables:
            doc["tables"] = self.tables
        if self.title_block:
            doc["title_block"] = self.title_block
        return doc
