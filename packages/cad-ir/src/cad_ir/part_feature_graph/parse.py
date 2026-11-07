"""Parser and validation driver for Part Feature Graph IR (spec 5.7)."""

from typing import Any, cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.part_feature_graph.model import (
    PART_SCHEMA_ID,
    Arc,
    CenterRectangle,
    Circle,
    CircularPattern,
    CornerRectangle,
    CutRevolve,
    EndCondition,
    Line,
    LinearPattern,
    LinearPatternDirection,
    Mirror,
    PartGraph,
    PartNode,
    Revolve,
    SketchEntity,
    SketchNode,
    SolidNode,
    StraightSlot,
)


def _parse_sketch_entities(
    raw_entities: dict[str, dict[str, JsonValue]],
) -> dict[str, SketchEntity]:
    entities: dict[str, SketchEntity] = {}
    for ent_id, ent_data in raw_entities.items():
        ent_type = str(ent_data["type"])
        if ent_type == "line":
            raw_start = cast(list[float], ent_data["start"])
            raw_end = cast(list[float], ent_data["end"])
            construction = bool(ent_data.get("construction", False))
            entities[ent_id] = Line(
                start=(float(raw_start[0]), float(raw_start[1])),
                end=(float(raw_end[0]), float(raw_end[1])),
                construction=construction,
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
        elif ent_type == "corner_rectangle":
            raw_c1 = cast(list[float], ent_data["corner1"])
            raw_c2 = cast(list[float], ent_data["corner2"])
            entities[ent_id] = CornerRectangle(
                corner1=(float(raw_c1[0]), float(raw_c1[1])),
                corner2=(float(raw_c2[0]), float(raw_c2[1])),
            )
        elif ent_type == "center_rectangle":
            raw_center = cast(list[float], ent_data["center"])
            entities[ent_id] = CenterRectangle(
                center=(float(raw_center[0]), float(raw_center[1])),
                width=float(cast(float | int, ent_data["width"])),
                height=float(cast(float | int, ent_data["height"])),
            )
        elif ent_type == "straight_slot":
            raw_p1 = cast(list[float], ent_data["start_point"])
            raw_p2 = cast(list[float], ent_data["end_point"])
            entities[ent_id] = StraightSlot(
                start_point=(float(raw_p1[0]), float(raw_p1[1])),
                end_point=(float(raw_p2[0]), float(raw_p2[1])),
                width=float(cast(float | int, ent_data["width"])),
            )
    return entities


def _parse_linear_pattern(
    node_data: dict[str, JsonValue],
    dependencies: tuple[str, ...],
    display_name: str | None,
    realizes: tuple[str, ...],
) -> LinearPattern:
    raw_seeds = cast(list[str], node_data["seeds"])
    seeds = tuple(str(s) for s in raw_seeds)
    d1_data = cast(dict[str, JsonValue], node_data["direction_1"])
    dir1 = LinearPatternDirection(
        direction=str(d1_data["direction"]),
        spacing=float(cast(float | int, d1_data["spacing"])),
        count=int(cast(int, d1_data["count"])),
        reverse=bool(d1_data.get("reverse", False)),
    )
    dir2: LinearPatternDirection | None = None
    if "direction_2" in node_data and node_data["direction_2"] is not None:
        d2_data = cast(dict[str, JsonValue], node_data["direction_2"])
        dir2 = LinearPatternDirection(
            direction=str(d2_data["direction"]),
            spacing=float(cast(float | int, d2_data["spacing"])),
            count=int(cast(int, d2_data["count"])),
            reverse=bool(d2_data.get("reverse", False)),
        )
    return LinearPattern(
        seeds=seeds,
        direction_1=dir1,
        direction_2=dir2,
        dependencies=dependencies,
        display_name=display_name,
        realizes=realizes,
    )


def _parse_circular_pattern(
    node_data: dict[str, JsonValue],
    dependencies: tuple[str, ...],
    display_name: str | None,
    realizes: tuple[str, ...],
) -> CircularPattern:
    raw_seeds = cast(list[JsonValue], node_data["seeds"])
    seeds = tuple(str(s) for s in raw_seeds)
    axis = str(node_data.get("axis") or node_data.get("direction"))
    count = int(cast(int, node_data["count"]))
    spacing = float(cast(float | int, node_data["spacing"]))
    equal_spacing = bool(node_data.get("equal_spacing", True))
    reverse = bool(node_data.get("reverse", False))
    return CircularPattern(
        seeds=seeds,
        axis=axis,
        count=count,
        spacing=spacing,
        equal_spacing=equal_spacing,
        reverse=reverse,
        dependencies=dependencies,
        display_name=display_name,
        realizes=realizes,
    )


def _parse_mirror(
    node_data: dict[str, JsonValue],
    dependencies: tuple[str, ...],
    display_name: str | None,
    realizes: tuple[str, ...],
) -> Mirror:
    raw_seeds = cast(list[JsonValue], node_data["seeds"])
    seeds = tuple(str(s) for s in raw_seeds)
    plane = str(node_data["plane"])
    merge = bool(node_data.get("merge", True))
    return Mirror(
        seeds=seeds,
        plane=plane,
        merge=merge,
        dependencies=dependencies,
        display_name=display_name,
        realizes=realizes,
    )


def _parse_revolve(
    node_data: dict[str, JsonValue],
    dependencies: tuple[str, ...],
    display_name: str | None,
    realizes: tuple[str, ...],
) -> Revolve:
    profile = str(node_data["profile"])
    raw_axis = node_data.get("axis")
    axis = str(raw_axis) if raw_axis is not None else None
    angle = float(cast(float | int, node_data.get("angle", 360.0)))
    mid_plane = bool(node_data.get("mid_plane", False))
    reverse = bool(node_data.get("reverse", False))
    raw_thin = node_data.get("thin")
    thin = cast(dict[str, Any], raw_thin) if isinstance(raw_thin, dict) else None
    merge_result = bool(node_data.get("merge_result", True))
    return Revolve(
        profile=profile,
        axis=axis,
        angle=angle,
        mid_plane=mid_plane,
        reverse=reverse,
        thin=thin,
        merge_result=merge_result,
        dependencies=dependencies,
        display_name=display_name,
        realizes=realizes,
    )


def _parse_cut_revolve(
    node_data: dict[str, JsonValue],
    dependencies: tuple[str, ...],
    display_name: str | None,
    realizes: tuple[str, ...],
) -> CutRevolve:
    profile = str(node_data["profile"])
    raw_axis = node_data.get("axis")
    axis = str(raw_axis) if raw_axis is not None else None
    angle = float(cast(float | int, node_data.get("angle", 360.0)))
    mid_plane = bool(node_data.get("mid_plane", False))
    reverse = bool(node_data.get("reverse", False))
    raw_thin = node_data.get("thin")
    thin = cast(dict[str, Any], raw_thin) if isinstance(raw_thin, dict) else None
    return CutRevolve(
        profile=profile,
        axis=axis,
        angle=angle,
        mid_plane=mid_plane,
        reverse=reverse,
        thin=thin,
        dependencies=dependencies,
        display_name=display_name,
        realizes=realizes,
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
    nodes: dict[str, PartNode] = {}

    for node_id, node_data in nodes_dict.items():
        node_type = str(node_data["type"])
        raw_deps = node_data.get("dependencies")
        dependencies = tuple(str(d) for d in raw_deps) if isinstance(raw_deps, list) else ()
        raw_disp = node_data.get("display_name")
        display_name = str(raw_disp) if raw_disp is not None else None
        raw_realizes = node_data.get("realizes")
        realizes = tuple(str(r) for r in raw_realizes) if isinstance(raw_realizes, list) else ()

        if node_type == "sketch":
            raw_entities = cast(dict[str, dict[str, JsonValue]], node_data.get("entities", {}))
            nodes[node_id] = SketchNode(
                plane=str(node_data["plane"]),
                entities=_parse_sketch_entities(raw_entities),
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
        elif node_type == "linear_pattern":
            nodes[node_id] = _parse_linear_pattern(node_data, dependencies, display_name, realizes)
        elif node_type == "circular_pattern":
            nodes[node_id] = _parse_circular_pattern(
                node_data, dependencies, display_name, realizes
            )
        elif node_type == "mirror":
            nodes[node_id] = _parse_mirror(node_data, dependencies, display_name, realizes)
        elif node_type == "revolve":
            nodes[node_id] = _parse_revolve(node_data, dependencies, display_name, realizes)
        elif node_type == "cut_revolve":
            nodes[node_id] = _parse_cut_revolve(node_data, dependencies, display_name, realizes)

    return PartGraph(
        id=str(doc_dict["id"]),
        schema_version=str(doc_dict["schema_version"]),
        units=str(doc_dict["units"]),
        origin=str(doc_dict["origin"]),
        nodes=nodes,
    )
