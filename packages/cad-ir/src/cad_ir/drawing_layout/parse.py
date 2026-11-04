"""Parser and validation driver for Drawing Layout IR (spec 11.11)."""

from typing import Any, cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.drawing_layout.model import (
    LAYOUT_SCHEMA_ID,
    DrawingAnnotation,
    DrawingLayout,
    DrawingSheet,
    DrawingView,
    ViewDisplay,
)


def parse_drawing_layout(doc: dict[str, Any]) -> DrawingLayout | IssueReport:
    """Validate and parse a Drawing Layout IR document against schemas/drawing-layout/v0.json."""
    issues = list(validate_against_schema(cast(JsonValue, doc), LAYOUT_SCHEMA_ID))
    if issues:
        return build_report(issues)

    sheets: dict[str, DrawingSheet] = {}
    for sheet_id, sheet_dict in doc.get("sheets", {}).items():
        sheets[sheet_id] = DrawingSheet(
            size=sheet_dict.get("size"),
            orientation=sheet_dict.get("orientation"),
            scale=sheet_dict.get("scale"),
            sheet_format=sheet_dict.get("sheet_format"),
            template=sheet_dict.get("template"),
        )

    views: dict[str, DrawingView] = {}
    for view_id, view_dict in doc.get("views", {}).items():
        pos = view_dict.get("position", [0.0, 0.0])
        disp_dict = view_dict.get("display", {})
        display = ViewDisplay(
            hidden_lines=bool(disp_dict.get("hidden_lines", False)),
            tangent_edges=str(disp_dict.get("tangent_edges", "removed")),
        )
        views[view_id] = DrawingView(
            sheet=str(view_dict["sheet"]),
            type=str(view_dict["type"]),
            position=(float(pos[0]), float(pos[1])),
            scale=str(view_dict["scale"]),
            orientation=str(view_dict.get("orientation", "front")),
            configuration=str(view_dict.get("configuration", "Default")),
            parent=view_dict.get("parent"),
            display=display,
            label=view_dict.get("label"),
            modifiers=view_dict.get("modifiers", {}),
        )

    annotations: dict[str, DrawingAnnotation] = {}
    for ann_id, ann_dict in doc.get("annotations", {}).items():
        pos = ann_dict.get("text_position", [0.0, 0.0])
        annotations[ann_id] = DrawingAnnotation(
            kind=str(ann_dict["kind"]),
            view=str(ann_dict["view"]),
            text_position=(float(pos[0]), float(pos[1])),
            intent_ref=ann_dict.get("intent_ref"),
            tag=ann_dict.get("tag"),
            native_id=ann_dict.get("native_id"),
            placed_by=str(ann_dict.get("placed_by", "pipeline")),
            pinned=bool(ann_dict.get("pinned", False)),
            side=ann_dict.get("side"),
            offset=float(ann_dict["offset"]) if ann_dict.get("offset") is not None else None,
        )

    return DrawingLayout(
        id=str(doc["id"]),
        schema_version=str(doc["schema_version"]),
        units=str(doc["units"]),
        intent=str(doc["intent"]),
        sheets=sheets,
        views=views,
        annotations=annotations,
        revision=int(doc["revision"]) if doc.get("revision") is not None else None,
        part_path=doc.get("part_path"),
        drafting_standard=doc.get("drafting_standard"),
        template=doc.get("template"),
        tables=doc.get("tables", {}),
        title_block=doc.get("title_block", {}),
    )
