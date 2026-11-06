"""``validate_part_graph`` (spec 12.4.5, design 10): pure IR validation and expected geometry."""

from cad_compiler.graph.analyze import GraphCycleError, build_order
from cad_compiler.validator.semantic import validate_graph
from cad_ir.core.issues import IssueReport
from cad_ir.core.json_types import JsonValue
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_verification.part import ExpectedGeometry, expected_geometry

from cad_application.tools.context import Call, ToolContext
from cad_application.tools.result import ToolResult, ok


def _expected_to_json(geom: ExpectedGeometry) -> dict[str, JsonValue]:
    return {
        "solid_body_count": geom.solid_body_count,
        "bbox_mm": {
            "min": [geom.bbox_mm.min.x, geom.bbox_mm.min.y, geom.bbox_mm.min.z],
            "max": [geom.bbox_mm.max.x, geom.bbox_mm.max.y, geom.bbox_mm.max.z],
        },
        "volume_mm3": geom.volume_mm3,
        "surface_area_mm2": geom.surface_area_mm2,
        "center_of_mass_mm": [
            geom.center_of_mass_mm.x,
            geom.center_of_mass_mm.y,
            geom.center_of_mass_mm.z,
        ],
        "cylinders": [
            {
                "point": [c.point.x, c.point.y, c.point.z],
                "direction": [c.direction.x, c.direction.y, c.direction.z],
                "radius": c.radius,
            }
            for c in geom.cylinders
        ],
        "features": [{"node_id": f.node_id, "type": f.type} for f in geom.features],
    }


def handle(_ctx: ToolContext, call: Call) -> ToolResult:
    raw_graph = call.arguments["graph"]
    parsed = parse_part_graph(raw_graph)
    if isinstance(parsed, IssueReport):
        issues_json: list[JsonValue] = [i.to_json() for i in parsed.issues]
        data_err: JsonValue = {
            "valid": False,
            "issues": issues_json,
            "build_order": None,
            "expected": None,
        }
        return ok(data_err, call.ids(), f"part graph invalid: {len(issues_json)} issue(s)")

    semantic_issues = validate_graph(parsed)
    has_error = any(i.severity == "error" for i in semantic_issues)
    issues_list: list[JsonValue] = [i.to_json() for i in semantic_issues]

    order: list[JsonValue] | None = None
    expected_json: dict[str, JsonValue] | None = None
    if not has_error:
        try:
            order = list(build_order(parsed))
            geom = expected_geometry(parsed)
            expected_json = _expected_to_json(geom)
        except (GraphCycleError, ValueError):
            has_error = True

    valid = not has_error and order is not None and expected_json is not None
    data: JsonValue = {
        "valid": valid,
        "issues": issues_list,
        "build_order": order,
        "expected": expected_json,
    }
    if valid and expected_json is not None and order is not None:
        vol = expected_json["volume_mm3"]
        summary = f"part graph valid: {len(order)} feature(s), volume {vol:.2f} mm3"
    else:
        summary = f"part graph invalid: {len(issues_list)} issue(s)"
    return ok(data, call.ids(), summary)
