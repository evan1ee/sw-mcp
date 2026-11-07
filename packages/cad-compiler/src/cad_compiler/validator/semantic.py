"""Semantic validator for Part Feature Graph IR (spec 5.7, 6.7.2)."""

import math
from collections.abc import Sequence
from typing import Final

from cad_ir.core.issues import ValidationIssue, issue_sort_key
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.faces import SUPPORTED_ROLES, in_base_frame, parse_face_plane
from cad_ir.part_feature_graph.model import (
    Arc,
    CenterRectangle,
    Circle,
    CornerRectangle,
    Line,
    PartGraph,
    SketchEntity,
    SketchNode,
    SolidNode,
    StraightSlot,
)

from cad_compiler.graph.analyze import analyze_graph, resolve_dependencies

_QUANTUM: Final[float] = 1e-6
_MIN_CIRCLE_DIA: Final[float] = 0.01
_TOL: Final[float] = 1e-12
_LOOP_DEGREE: Final[int] = 2
_FOUR_VERTICES: Final[int] = 4


def _ccw(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """Check if open segments (p1, p2) and (p3, p4) strictly intersect."""
    d1 = _ccw(p1, p2, p3)
    d2 = _ccw(p1, p2, p4)
    d3 = _ccw(p3, p4, p1)
    d4 = _ccw(p3, p4, p2)

    cond1 = (d1 > _TOL and d2 < -_TOL) or (d1 < -_TOL and d2 > _TOL)
    cond2 = (d3 > _TOL and d4 < -_TOL) or (d3 < -_TOL and d4 > _TOL)
    return cond1 and cond2


def _dist_point_to_segment(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    len_sq = dx * dx + dy * dy
    if len_sq < _TOL:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len_sq))
    proj_x = a[0] + t * dx
    proj_y = a[1] + t * dy
    return math.hypot(p[0] - proj_x, p[1] - proj_y)


def _point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(polygon)
    for i in range(n):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % n]
        if (p1[1] <= py < p2[1]) or (p2[1] <= py < p1[1]):
            x_int = p1[0] + (py - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1])
            if x_int > px:
                inside = not inside
    return inside


def _is_connected(edges: list[tuple[int, int]]) -> bool:
    """Return True when every edge belongs to one connected component."""
    adjacency: dict[int, list[int]] = {}
    for u, v in edges:
        adjacency.setdefault(u, []).append(v)
        adjacency.setdefault(v, []).append(u)
    start = next(iter(adjacency))
    seen = {start}
    stack = [start]
    while stack:
        for nxt in adjacency[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen) == len(adjacency)


def _validate_curves_loop(curves: Sequence[Line | Arc], pointer: str) -> list[ValidationIssue]:
    """Validate that lines and arcs form a single non-self-intersecting closed loop."""
    issues: list[ValidationIssue] = []
    if not curves:
        return issues

    pts: list[tuple[float, float]] = []

    def get_vertex(pt: tuple[float, float]) -> int:
        for idx, v in enumerate(pts):
            if math.hypot(pt[0] - v[0], pt[1] - v[1]) <= _QUANTUM:
                return idx
        pts.append(pt)
        return len(pts) - 1

    edges: list[tuple[int, int]] = []
    for curve in curves:
        u = get_vertex(curve.start)
        v = get_vertex(curve.end)
        edges.append((u, v))

    deg: dict[int, int] = {}
    for u, v in edges:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1

    if (
        any(d != _LOOP_DEGREE for d in deg.values())
        or len(deg) != len(edges)
        or not _is_connected(edges)
    ):
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=pointer,
                message=(
                    "Sketch lines and arcs must form a single closed loop within 3.4.3"
                    " quantum: each end point must meet exactly one other entity and all"
                    " entities must be connected"
                ),
            )
        )
        return issues

    lines = [c for c in curves if isinstance(c, Line)]
    n = len(lines)
    for i in range(n):
        for j in range(i + 1, n):
            u1, v1 = get_vertex(lines[i].start), get_vertex(lines[i].end)
            u2, v2 = get_vertex(lines[j].start), get_vertex(lines[j].end)
            if len({u1, v1, u2, v2}) < _FOUR_VERTICES:
                continue
            if _segments_intersect(lines[i].start, lines[i].end, lines[j].start, lines[j].end):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=pointer,
                        message="Sketch lines loop cannot be self-intersecting",
                    )
                )
                return issues

    return issues


def _validate_lines_loop(lines: list[Line], pointer: str) -> list[ValidationIssue]:  # pyright: ignore[reportUnusedFunction]
    return _validate_curves_loop(lines, pointer)


def _check_headers(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    if graph.units != "mm":
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/units",
                message="Units must be 'mm'",
            )
        )
    if graph.origin != "built":
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/origin",
                message="Origin must be 'built'",
            )
        )


_STANDARD_PLANES: Final = ("plane:front", "plane:top", "plane:right")


def _check_face_planes(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    """A sketch may sit on an origin plane or on the start or end face of the extrude (ADR-070)."""
    for node_id, node in graph.nodes.items():
        if not isinstance(node, SketchNode) or node.plane in _STANDARD_PLANES:
            continue
        face = parse_face_plane(node.plane)
        if face is None:
            continue  # other hosts are rejected at lowering
        pointer = f"/nodes/{node_id}/plane"
        host = graph.nodes.get(face.node_id)
        if face.role not in SUPPORTED_ROLES:
            message = f"Face '{face.role}' is not supported: use start_face or end_face"
            issues.append(ValidationIssue(ErrorCode.IR_RULE_VIOLATED, pointer, message))
        elif host is None:
            message = f"Face reference '{node.plane}': node '{face.node_id}' not found in graph"
            issues.append(
                ValidationIssue(
                    ErrorCode.IR_REFERENCE_UNRESOLVED, pointer, message, ref=face.node_id
                )
            )
        elif not (isinstance(host, SolidNode) and host.type == "extrude"):
            message = f"Face reference '{node.plane}': '{face.node_id}' must be the extrude"
            issues.append(ValidationIssue(ErrorCode.IR_RULE_VIOLATED, pointer, message))
        elif face.node_id not in node.dependencies:
            message = (
                f"Sketch on '{node.plane}' must depend on '{face.node_id}':"
                " add the extrude to its dependencies"
            )
            issues.append(
                ValidationIssue(
                    ErrorCode.IR_RULE_VIOLATED, f"/nodes/{node_id}/dependencies", message
                )
            )


def _check_references(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    for node_id, node in graph.nodes.items():
        if isinstance(node, SolidNode):
            if node.profile not in graph.nodes:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_REFERENCE_UNRESOLVED,
                        pointer=f"/nodes/{node_id}/profile",
                        message=f"Profile '{node.profile}' not found in graph",
                        ref=node.profile,
                    )
                )
            elif not isinstance(graph.nodes[node.profile], SketchNode):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/nodes/{node_id}/profile",
                        message=f"Profile '{node.profile}' must be a sketch",
                    )
                )
        for dep in node.dependencies:
            if dep not in graph.nodes:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_REFERENCE_UNRESOLVED,
                        pointer=f"/nodes/{node_id}/dependencies",
                        message=f"Dependency '{dep}' not found in graph",
                        ref=dep,
                    )
                )


def _check_solids(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    solid_nodes = [(nid, n) for nid, n in graph.nodes.items() if isinstance(n, SolidNode)]
    extrudes = [(nid, n) for nid, n in solid_nodes if n.type == "extrude"]
    cuts = [(nid, n) for nid, n in solid_nodes if n.type == "cut_extrude"]

    if len(extrudes) > 1:
        for ext_id, _ in extrudes[1:]:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{ext_id}/type",
                    message="Only one extrude feature is allowed: remove the extra extrude",
                )
            )

    extrude_node_id = extrudes[0][0] if extrudes else None
    extrude_node = extrudes[0][1] if extrudes else None
    deps_map = resolve_dependencies(graph)

    def get_transitive_deps(start: str) -> set[str]:
        visited: set[str] = set()
        queue = list(deps_map.get(start, set()))
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                queue.extend(deps_map.get(curr, set()))
        return visited

    for cut_id, _ in cuts:
        trans_deps = get_transitive_deps(cut_id)
        if extrude_node_id is None or extrude_node_id not in trans_deps:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{cut_id}/dependencies",
                    message=(
                        f"Cut feature '{cut_id}' must depend on the extrude feature:"
                        " add the extrude to its dependencies"
                    ),
                )
            )

    for s_id, s_node in solid_nodes:
        if s_node.end_condition.depth is not None:
            if s_node.end_condition.depth <= 0:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/nodes/{s_id}/end_condition/depth",
                        message="Feature depth must be positive",
                    )
                )
            elif (
                s_node.type == "cut_extrude"
                and extrude_node is not None
                and extrude_node.end_condition.depth is not None
                and s_node.end_condition.depth >= extrude_node.end_condition.depth
            ):
                depth_limit = extrude_node.end_condition.depth
                msg = f"Cut depth must be less than extrude depth ({depth_limit})"
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/nodes/{s_id}/end_condition/depth",
                        message=msg,
                    )
                )


def _rect_to_lines(rect: CornerRectangle | CenterRectangle) -> list[Line]:
    if isinstance(rect, CornerRectangle):
        xmin = min(rect.corner1[0], rect.corner2[0])
        xmax = max(rect.corner1[0], rect.corner2[0])
        ymin = min(rect.corner1[1], rect.corner2[1])
        ymax = max(rect.corner1[1], rect.corner2[1])
    else:
        hw = rect.width / 2.0
        hh = rect.height / 2.0
        xmin = rect.center[0] - hw
        xmax = rect.center[0] + hw
        ymin = rect.center[1] - hh
        ymax = rect.center[1] + hh
    return [
        Line(start=(xmin, ymin), end=(xmax, ymin)),
        Line(start=(xmax, ymin), end=(xmax, ymax)),
        Line(start=(xmax, ymax), end=(xmin, ymax)),
        Line(start=(xmin, ymax), end=(xmin, ymin)),
    ]


def _slot_to_curves(slot: StraightSlot) -> list[Line | Arc]:
    p1 = slot.start_point
    p2 = slot.end_point
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < _QUANTUM:
        return []
    r = slot.width / 2.0
    nx = -dy / length
    ny = dx / length
    ox = r * nx
    oy = r * ny
    l1_start = (p1[0] - ox, p1[1] - oy)
    l1_end = (p2[0] - ox, p2[1] - oy)
    l2_start = (p2[0] + ox, p2[1] + oy)
    l2_end = (p1[0] + ox, p1[1] + oy)
    return [
        Line(start=l1_start, end=l1_end),
        Arc(center=p2, start=l1_end, end=l2_start, direction="ccw"),
        Line(start=l2_start, end=l2_end),
        Arc(center=p1, start=l2_end, end=l1_start, direction="ccw"),
    ]


def _check_arc(s_id: str, ent_id: str, ent: Arc, issues: list[ValidationIssue]) -> None:
    r_start = math.hypot(ent.start[0] - ent.center[0], ent.start[1] - ent.center[1])
    r_end = math.hypot(ent.end[0] - ent.center[0], ent.end[1] - ent.center[1])
    if abs(r_start - r_end) > _QUANTUM:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{s_id}/entities/{ent_id}",
                message=f"Arc '{ent_id}' start and end points must have equal radius from center",
            )
        )
    if r_start < _MIN_CIRCLE_DIA - _TOL:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{s_id}/entities/{ent_id}",
                message=f"Arc '{ent_id}' radius must be at least 0.01 mm",
            )
        )
    if math.hypot(ent.end[0] - ent.start[0], ent.end[1] - ent.start[1]) < _QUANTUM:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{s_id}/entities/{ent_id}",
                message=(
                    f"Arc '{ent_id}' start and end points cannot be coincident:"
                    " use a circle instead"
                ),
            )
        )


def _check_slot(s_id: str, ent_id: str, ent: StraightSlot, issues: list[ValidationIssue]) -> None:
    dx = ent.end_point[0] - ent.start_point[0]
    dy = ent.end_point[1] - ent.start_point[1]
    length = math.hypot(dx, dy)
    if length < _MIN_CIRCLE_DIA - _TOL:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{s_id}/entities/{ent_id}",
                message=f"Straight slot '{ent_id}' centerline length must be at least 0.01 mm",
            )
        )
    if ent.width < _MIN_CIRCLE_DIA - _TOL:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{s_id}/entities/{ent_id}",
                message=f"Straight slot '{ent_id}' width must be at least 0.01 mm",
            )
        )


def _check_sketch_entity(
    s_id: str, ent_id: str, ent: SketchEntity, issues: list[ValidationIssue]
) -> None:
    if isinstance(ent, Line):
        dx = ent.end[0] - ent.start[0]
        dy = ent.end[1] - ent.start[1]
        if math.hypot(dx, dy) < _QUANTUM:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{s_id}/entities/{ent_id}",
                    message=f"Line '{ent_id}' cannot have zero length",
                )
            )
    elif isinstance(ent, Circle):
        if ent.diameter < _MIN_CIRCLE_DIA - _TOL:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{s_id}/entities/{ent_id}/diameter",
                    message=f"Circle '{ent_id}' diameter must be at least 0.01 mm",
                )
            )
    elif isinstance(ent, Arc):
        _check_arc(s_id, ent_id, ent, issues)
    elif isinstance(ent, CornerRectangle):
        w = abs(ent.corner2[0] - ent.corner1[0])
        h = abs(ent.corner2[1] - ent.corner1[1])
        if w < _MIN_CIRCLE_DIA - _TOL or h < _MIN_CIRCLE_DIA - _TOL:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{s_id}/entities/{ent_id}",
                    message=(f"Rectangle '{ent_id}' width and height must be at least 0.01 mm"),
                )
            )
    elif isinstance(ent, CenterRectangle):
        if ent.width < _MIN_CIRCLE_DIA - _TOL or ent.height < _MIN_CIRCLE_DIA - _TOL:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{s_id}/entities/{ent_id}",
                    message=(f"Rectangle '{ent_id}' width and height must be at least 0.01 mm"),
                )
            )
    else:
        _check_slot(s_id, ent_id, ent, issues)


def _check_sketches(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    for s_id, node in graph.nodes.items():
        if not isinstance(node, SketchNode):
            continue
        curves: list[Line | Arc] = [e for e in node.entities.values() if isinstance(e, (Line, Arc))]
        for ent in node.entities.values():
            if isinstance(ent, (CornerRectangle, CenterRectangle)):
                curves.extend(_rect_to_lines(ent))
            elif isinstance(ent, StraightSlot):
                curves.extend(_slot_to_curves(ent))
        if curves:
            issues.extend(_validate_curves_loop(curves, f"/nodes/{s_id}/entities"))
        for ent_id, ent in node.entities.items():
            _check_sketch_entity(s_id, ent_id, ent, issues)


def _check_extrude_profile(
    extrude_node_id: str,
    extrude_sketch: SketchNode,
    issues: list[ValidationIssue],
) -> None:
    ext_curves = [e for e in extrude_sketch.entities.values() if isinstance(e, (Line, Arc))]
    ext_circles = [e for e in extrude_sketch.entities.values() if isinstance(e, Circle)]
    ext_rects = [
        e
        for e in extrude_sketch.entities.values()
        if isinstance(e, (CornerRectangle, CenterRectangle))
    ]
    ext_slots = [e for e in extrude_sketch.entities.values() if isinstance(e, StraightSlot)]
    types_count = bool(ext_curves) + bool(ext_circles) + bool(ext_rects) + bool(ext_slots)
    if types_count > 1:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{extrude_node_id}/profile",
                message=(
                    "Extrude profile cannot mix circles, rectangles, slots, and line/arc curves"
                ),
            )
        )
    elif len(ext_circles) > 1:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{extrude_node_id}/profile",
                message="Extrude profile cannot have multiple circles",
            )
        )
    elif len(ext_rects) > 1:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{extrude_node_id}/profile",
                message="Extrude profile cannot have multiple rectangles",
            )
        )
    elif len(ext_slots) > 1:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{extrude_node_id}/profile",
                message="Extrude profile cannot have multiple slots",
            )
        )


def _chain_lines_into_loop(lines: list[Line]) -> list[tuple[float, float]]:
    """Chain line segments into an ordered directed vertex loop."""
    if not lines:
        return []
    remaining = list(lines)
    first = remaining.pop(0)
    loop: list[tuple[float, float]] = [first.start]
    curr = first.end

    while remaining:
        found = False
        for idx, line in enumerate(remaining):
            if math.hypot(line.start[0] - curr[0], line.start[1] - curr[1]) <= _QUANTUM:
                loop.append(curr)
                curr = line.end
                remaining.pop(idx)
                found = True
                break
            if math.hypot(line.end[0] - curr[0], line.end[1] - curr[1]) <= _QUANTUM:
                loop.append(curr)
                curr = line.start
                remaining.pop(idx)
                found = True
                break
        if not found:
            loop.append(curr)
            for r in remaining:
                loop.append(r.start)
            break

    return loop


def _sketch_lines(sketch: SketchNode) -> list[Line]:
    lines = [e for e in sketch.entities.values() if isinstance(e, Line)]
    for e in sketch.entities.values():
        if isinstance(e, (CornerRectangle, CenterRectangle)):
            lines.extend(_rect_to_lines(e))
        elif isinstance(e, StraightSlot):
            curves = _slot_to_curves(e)
            lines.extend([c for c in curves if isinstance(c, Line)])
    return lines


def _sketch_circles(sketch: SketchNode) -> list[tuple[str, Circle]]:
    return [(eid, e) for eid, e in sketch.entities.items() if isinstance(e, Circle)]


def _clear_of_edges(point: tuple[float, float], lines: list[Line], margin: float) -> bool:
    return all(_dist_point_to_segment(point, ln.start, ln.end) > margin for ln in lines)


def _strictly_inside_loop(point: tuple[float, float], lines: list[Line]) -> bool:
    loop = _chain_lines_into_loop(lines)
    return _point_in_polygon(point[0], point[1], loop) and _clear_of_edges(point, lines, _QUANTUM)


def _loop_sample_points(lines: list[Line]) -> list[tuple[float, float]]:
    """Vertices and edge midpoints of a loop, plus one point inside it.

    The inside point comes from a horizontal line between two vertex heights: the first two
    crossings of a simple loop bound a stretch of its interior.
    """
    points = [ln.start for ln in lines]
    points += [((ln.start[0] + ln.end[0]) / 2.0, (ln.start[1] + ln.end[1]) / 2.0) for ln in lines]
    heights = sorted({p[1] for ln in lines for p in (ln.start, ln.end)})
    if len(heights) > 1:
        y = (heights[0] + heights[1]) / 2.0
        xs = sorted(
            ln.start[0] + (y - ln.start[1]) * (ln.end[0] - ln.start[0]) / (ln.end[1] - ln.start[1])
            for ln in lines
            if (ln.start[1] <= y < ln.end[1]) or (ln.end[1] <= y < ln.start[1])
        )
        if len(xs) > 1:
            points.append(((xs[0] + xs[1]) / 2.0, y))
    return points


def _edges_cross(first: list[Line], second: list[Line]) -> bool:
    return any(_segments_intersect(a.start, a.end, b.start, b.end) for a in first for b in second)


def _circle_inside_base(circle: Circle, base: SketchNode) -> bool:
    radius = circle.diameter / 2.0
    lines = _sketch_lines(base)
    if lines:
        return _strictly_inside_loop(circle.center, lines) and _clear_of_edges(
            circle.center, lines, radius + _QUANTUM
        )
    return all(
        math.hypot(circle.center[0] - outer.center[0], circle.center[1] - outer.center[1]) + radius
        < outer.diameter / 2.0 - _QUANTUM
        for _, outer in _sketch_circles(base)
    )


def _loop_inside_base(loop: list[Line], base: SketchNode) -> bool:
    lines = _sketch_lines(base)
    samples = _loop_sample_points(loop)
    if lines:
        return not _edges_cross(loop, lines) and all(
            _strictly_inside_loop(p, lines) for p in samples
        )
    return all(
        math.hypot(p[0] - outer.center[0], p[1] - outer.center[1]) < outer.diameter / 2.0 - _QUANTUM
        for p in samples
        for _, outer in _sketch_circles(base)
    )


def _check_cut_inside_base(
    cut_prof_id: str,
    cut_sketch: SketchNode,
    base: SketchNode,
    issues: list[ValidationIssue],
) -> None:
    """A cut lies strictly inside the base profile, so the part stays one exact body."""
    for eid, circle in _sketch_circles(cut_sketch):
        if not _circle_inside_base(circle, base):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{cut_prof_id}/entities/{eid}",
                    message=(
                        f"Hole '{eid}' is tangent to or outside the extrude profile:"
                        " move it inside so it does not touch the edge"
                    ),
                )
            )
    loop = _sketch_lines(cut_sketch)
    if loop and not _loop_inside_base(loop, base):
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{cut_prof_id}/entities",
                message=(
                    "Cut loop is not strictly inside the extrude profile:"
                    " move it inside so it does not touch the edge"
                ),
            )
        )


def _circles_overlap(first: Circle, second: Circle) -> bool:
    distance = math.hypot(first.center[0] - second.center[0], first.center[1] - second.center[1])
    return distance < first.diameter / 2.0 + second.diameter / 2.0 - _QUANTUM


def _circle_overlaps_loop(circle: Circle, loop: list[Line]) -> bool:
    radius = circle.diameter / 2.0
    return _strictly_inside_loop(circle.center, loop) or not _clear_of_edges(
        circle.center, loop, radius - _QUANTUM
    )


def _loops_overlap(first: list[Line], second: list[Line]) -> bool:
    if _edges_cross(first, second):
        return True
    return any(_strictly_inside_loop(p, second) for p in _loop_sample_points(first)) or any(
        _strictly_inside_loop(p, first) for p in _loop_sample_points(second)
    )


def _profiles_overlap(first: SketchNode, second: SketchNode) -> bool:
    first_loop, second_loop = _sketch_lines(first), _sketch_lines(second)
    first_circles = [c for _, c in _sketch_circles(first)]
    second_circles = [c for _, c in _sketch_circles(second)]
    return (
        bool(first_loop and second_loop and _loops_overlap(first_loop, second_loop))
        or any(_circles_overlap(a, b) for a in first_circles for b in second_circles)
        or any(_circle_overlaps_loop(c, second_loop) for c in first_circles if second_loop)
        or any(_circle_overlaps_loop(c, first_loop) for c in second_circles if first_loop)
    )


def _check_cuts_do_not_overlap(
    cuts: list[tuple[str, SolidNode]],
    graph: PartGraph,
    issues: list[ValidationIssue],
) -> None:
    """Separate cuts remove separate material, or expected geometry would count it twice."""
    profiled = [
        (cut_id, cut.profile, profile)
        for cut_id, cut in cuts
        if isinstance(profile := graph.nodes.get(cut.profile), SketchNode)
    ]
    for index, (first_id, first_profile_id, first) in enumerate(profiled):
        for second_id, second_profile_id, second in profiled[index + 1 :]:
            if first_profile_id == second_profile_id or _profiles_overlap(first, second):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/nodes/{second_id}/profile",
                        message=f"Cut '{second_id}' overlaps cut '{first_id}'",
                    )
                )


def _check_cut_profiles(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    extrudes = [n for n in graph.nodes.values() if isinstance(n, SolidNode) and n.type == "extrude"]
    extrude_sketch = None
    if extrudes and extrudes[0].profile in graph.nodes:
        prof = graph.nodes[extrudes[0].profile]
        if isinstance(prof, SketchNode):
            extrude_sketch = prof

    cuts = [
        (nid, n)
        for nid, n in graph.nodes.items()
        if isinstance(n, SolidNode) and n.type == "cut_extrude"
    ]
    for _, cut_node in cuts:
        if cut_node.profile not in graph.nodes:
            continue
        cut_prof = graph.nodes[cut_node.profile]
        if not isinstance(cut_prof, SketchNode):
            continue

        if (
            extrude_sketch is not None
            and cut_prof.plane != extrude_sketch.plane
            and parse_face_plane(cut_prof.plane) is None
        ):
            msg = (
                f"Cut sketch plane '{cut_prof.plane}' "
                f"must match extrude plane '{extrude_sketch.plane}'"
            )
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{cut_node.profile}/plane",
                    message=msg,
                )
            )

        cut_circles = [(eid, e) for eid, e in cut_prof.entities.items() if isinstance(e, Circle)]
        for i in range(len(cut_circles)):
            id1, c1 = cut_circles[i]
            r1 = c1.diameter / 2.0
            for j in range(i + 1, len(cut_circles)):
                id2, c2 = cut_circles[j]
                r2 = c2.diameter / 2.0
                dist = math.hypot(c1.center[0] - c2.center[0], c1.center[1] - c2.center[1])
                if dist < r1 + r2 - _QUANTUM:
                    issues.append(
                        ValidationIssue(
                            code=ErrorCode.IR_RULE_VIOLATED,
                            pointer=f"/nodes/{cut_node.profile}/entities/{id2}",
                            message=f"Circle '{id2}' overlaps with circle '{id1}'",
                        )
                    )

        if cut_circles and _sketch_lines(cut_prof):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{cut_node.profile}/entities",
                    message="Cut profile cannot mix lines and circles",
                )
            )
        elif extrude_sketch is not None:
            _check_cut_inside_base(cut_node.profile, cut_prof, extrude_sketch, issues)

    _check_cuts_do_not_overlap(cuts, graph, issues)


def validate_graph(graph: PartGraph) -> tuple[ValidationIssue, ...]:
    """Validate semantic rules of a Part Feature Graph (spec 5.7, 6.7.2).

    All semantic issues are collected and returned deterministically sorted.
    """
    issues: list[ValidationIssue] = []

    _check_headers(graph, issues)
    _check_references(graph, issues)
    _check_face_planes(graph, issues)

    analysis = analyze_graph(graph)
    if analysis.cycle is not None:
        for node_id in analysis.cycle:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_CYCLE,
                    pointer=f"/nodes/{node_id}/dependencies",
                    message=f"Dependency cycle involving node '{node_id}'",
                )
            )

    _check_solids(graph, issues)
    _check_sketches(graph, issues)

    extrudes = [
        (nid, n)
        for nid, n in graph.nodes.items()
        if isinstance(n, SolidNode) and n.type == "extrude"
    ]
    if extrudes and extrudes[0][1].profile in graph.nodes:
        prof_node = graph.nodes[extrudes[0][1].profile]
        if isinstance(prof_node, SketchNode):
            _check_extrude_profile(extrudes[0][0], prof_node, issues)

    _check_cut_profiles(in_base_frame(graph), issues)

    return tuple(sorted(issues, key=issue_sort_key))
