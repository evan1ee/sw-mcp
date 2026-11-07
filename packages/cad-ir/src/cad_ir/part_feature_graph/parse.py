"""Parser and validation driver for Part Feature Graph IR (spec 5.7)."""

from typing import cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.part_feature_graph.model import (
    PART_SCHEMA_ID,
    Arc,
    Circle,
    EndCondition,
    Line,
    PartGraph,
    SketchNode,
    SolidNode,
)


def parse_part_graph(doc: JsonValue) -> PartGraph | IssueReport:
    """Validate and parse a Part Feature Graph IR document.

    Validates against schemas/part-feature-graph/v0.json.
    """
    issues = list(validate_against_schema(doc, PART_SCHEMA_ID))
    if issues:
        return build_report(issues)

    doc_dict = cast(dict[str, JsonValue], doc)
    nodes_dict = cast(dict[str, dict[str, JsonValue]], doc_dict.get("nodes", {}))
    nodes: dict[str, SketchNode | SolidNode] = {}

    for node_id, node_data in nodes_dict.items():
        node_type = str(node_data["type"])
        raw_deps = node_data.get("dependencies")
        dependencies = tuple(str(d) for d in raw_deps) if isinstance(raw_deps, list) else ()
        raw_disp = node_data.get("display_name")
        display_name = str(raw_disp) if raw_disp is not None else None
        raw_realizes = node_data.get("realizes")
        realizes = tuple(str(r) for r in raw_realizes) if isinstance(raw_realizes, list) else ()

        if node_type == "sketch":
            entities: dict[str, Line | Circle | Arc] = {}
            raw_entities = cast(dict[str, dict[str, JsonValue]], node_data.get("entities", {}))
            for ent_id, ent_data in raw_entities.items():
                ent_type = str(ent_data["type"])
                if ent_type == "line":
                    raw_start = cast(list[float], ent_data["start"])
                    raw_end = cast(list[float], ent_data["end"])
                    entities[ent_id] = Line(
                        start=(float(raw_start[0]), float(raw_start[1])),
                        end=(float(raw_end[0]), float(raw_end[1])),
                    )
                elif ent_type == "circle":
                    raw_center = cast(list[float], ent_data["center"])
                    entities[ent_id] = Circle(
                        center=(float(raw_center[0]), float(raw_center[1])),
                        diameter=float(cast(float | int, ent_data["diameter"])),
                    )
                elif ent_type == "arc":
                    raw_center = cast(list[float], ent_data["center"])
                    raw_start = cast(list[float], ent_data["start"])
                    raw_end = cast(list[float], ent_data["end"])
                    entities[ent_id] = Arc(
                        center=(float(raw_center[0]), float(raw_center[1])),
                        start=(float(raw_start[0]), float(raw_start[1])),
                        end=(float(raw_end[0]), float(raw_end[1])),
                        direction=str(ent_data["direction"]),
                    )
            nodes[node_id] = SketchNode(
                plane=str(node_data["plane"]),
                entities=entities,
                dependencies=dependencies,
                display_name=display_name,
                realizes=realizes,
            )
        elif node_type in ("extrude", "cut_extrude"):
            ec_data = cast(dict[str, JsonValue], node_data["end_condition"])
            ec_type = str(ec_data["type"])
            raw_depth = ec_data.get("depth")
            depth = float(cast(float | int, raw_depth)) if raw_depth is not None else None
            end_condition = EndCondition(type=ec_type, depth=depth)
            nodes[node_id] = SolidNode(
                type=node_type,
                profile=str(node_data["profile"]),
                end_condition=end_condition,
                dependencies=dependencies,
                display_name=display_name,
                realizes=realizes,
            )

    return PartGraph(
        id=str(doc_dict["id"]),
        schema_version=str(doc_dict["schema_version"]),
        units=str(doc_dict["units"]),
        origin=str(doc_dict["origin"]),
        nodes=nodes,
    )
