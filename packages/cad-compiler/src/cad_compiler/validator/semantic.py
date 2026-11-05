"""Semantic validator for Part Feature Graph IR (spec 5.7, 6.7.2)."""

import math
from typing import Final

from cad_ir.core.issues import ValidationIssue, issue_sort_key
from cad_ir.generated import ErrorCode
from cad_ir.part_feature_graph.model import Circle, Line, PartGraph, SketchNode, SolidNode

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


def _validate_lines_loop(lines: list[Line], pointer: str) -> list[ValidationIssue]:
    """Validate that lines form a single non-self-intersecting closed loop."""
    issues: list[ValidationIssue] = []
    if not lines:
        return issues

    pts: list[tuple[float, float]] = []

    def get_vertex(pt: tuple[float, float]) -> int:
        for idx, v in enumerate(pts):
            if math.hypot(pt[0] - v[0], pt[1] - v[1]) <= _QUANTUM:
                return idx
        pts.append(pt)
        return len(pts) - 1

    edges: list[tuple[int, int]] = []
    for line in lines:
        u = get_vertex(line.start)
        v = get_vertex(line.end)
        edges.append((u, v))

    deg: dict[int, int] = {}
    for u, v in edges:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1

    if any(d != _LOOP_DEGREE for d in deg.values()) or len(deg) != len(edges):
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=pointer,
                message="Sketch lines must form a single closed loop within 3.4.3 quantum",
            )
        )
        return issues

    n = len(lines)
    for i in range(n):
        for j in range(i + 1, n):
            u1, v1 = edges[i]
            u2, v2 = edges[j]
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
                    message="Only one extrude feature is allowed",
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
                    message=f"Cut feature '{cut_id}' must depend on the extrude feature",
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


def _check_sketches(graph: PartGraph, issues: list[ValidationIssue]) -> None:
    for s_id, node in graph.nodes.items():
        if not isinstance(node, SketchNode):
            continue
        lines = [e for e in node.entities.values() if isinstance(e, Line)]
        if lines:
            issues.extend(_validate_lines_loop(lines, f"/nodes/{s_id}/entities"))
        for ent_id, ent in node.entities.items():
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
            elif ent.diameter < _MIN_CIRCLE_DIA - _TOL:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/nodes/{s_id}/entities/{ent_id}/diameter",
                        message=f"Circle '{ent_id}' diameter must be at least 0.01 mm",
                    )
                )


def _check_extrude_profile(
    extrude_node_id: str,
    extrude_sketch: SketchNode,
    issues: list[ValidationIssue],
) -> None:
    ext_lines = [e for e in extrude_sketch.entities.values() if isinstance(e, Line)]
    ext_circles = [e for e in extrude_sketch.entities.values() if isinstance(e, Circle)]
    if ext_circles and ext_lines:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer=f"/nodes/{extrude_node_id}/profile",
                message="Extrude profile cannot mix lines and circles",
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


def _check_cut_circles_inside(
    cut_prof_id: str,
    cut_circles: list[tuple[str, Circle]],
    extrude_sketch: SketchNode,
    issues: list[ValidationIssue],
) -> None:
    ext_lines = [e for e in extrude_sketch.entities.values() if isinstance(e, Line)]
    if not ext_lines:
        return
    poly_pts = [line.start for line in ext_lines]
    for eid, circ in cut_circles:
        r = circ.diameter / 2.0
        cx, cy = circ.center
        inside = _point_in_polygon(cx, cy, poly_pts)
        min_dist = min(_dist_point_to_segment((cx, cy), line.start, line.end) for line in ext_lines)
        if not inside or min_dist <= r + _QUANTUM:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/nodes/{cut_prof_id}/entities/{eid}",
                    message=f"Hole '{eid}' is tangent to or outside the extrude profile",
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

        if extrude_sketch is not None and cut_prof.plane != extrude_sketch.plane:
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

        if extrude_sketch is not None:
            _check_cut_circles_inside(cut_node.profile, cut_circles, extrude_sketch, issues)


def validate_graph(graph: PartGraph) -> tuple[ValidationIssue, ...]:
    """Validate semantic rules of a Part Feature Graph (spec 5.7, 6.7.2).

    All semantic issues are collected and returned deterministically sorted.
    """
    issues: list[ValidationIssue] = []

    _check_headers(graph, issues)
    _check_references(graph, issues)

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

    _check_cut_profiles(graph, issues)

    return tuple(sorted(issues, key=issue_sort_key))
