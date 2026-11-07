"""CAD part verification core: expected geometry computation and measurement comparison."""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, NamedTuple, cast

from cad_ir.core.json_types import JsonValue
from cad_ir.part_feature_graph.faces import FaceFrame, face_frame, parse_face_plane
from cad_ir.part_feature_graph.model import (
    Arc,
    CenterRectangle,
    Circle,
    CircularPattern,
    CornerRectangle,
    CutRevolve,
    Line,
    LinearPattern,
    LinearPatternDirection,
    Mirror,
    PartGraph,
    Revolve,
    SketchNode,
    SolidNode,
    StraightSlot,
)
from cad_ir.part_feature_graph.planes import PlaneAxes, plane_axes

PARALLEL_DOT_TOLERANCE = 1e-4
LINEAR_TOLERANCE_MM = 0.01
RELATIVE_TOLERANCE_RATIO = 0.0001
DIM_3D = 3
MM_PER_M = 1000.0
MM2_PER_M2 = 1e6
MM3_PER_M3 = 1e9
MIN_PATTERN_COUNT = 2
REVOLVE_AXIS_TOL: Final[float] = 1e-5
REVOLVE_AREA_TOL: Final[float] = 1e-9
REVOLVE_PARALLEL_TOL: Final[float] = 1e-4
REVOLVE_RADIUS_TOL: Final[float] = 1e-3

type CheckStatus = Literal["passed", "failed", "warning", "not_applicable", "not_evaluated"]
type NotEvaluatedReason = Literal["not_executed", "unsupported", "missing_data", "malformed_data"]
type UnreadableReason = Literal["missing_data", "malformed_data"]

NOT_EVALUATED_REASONS: Final = frozenset(
    {"not_executed", "unsupported", "missing_data", "malformed_data"}
)


class Point3(NamedTuple):
    """3D point / vector in millimeters."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class Box:
    """Axis-aligned 3D bounding box in millimeters."""

    min: Point3
    max: Point3

    def __init__(
        self,
        min: Point3 | tuple[float, float, float] | list[float],
        max: Point3 | tuple[float, float, float] | list[float],
    ) -> None:
        p_min = (
            min if isinstance(min, Point3) else Point3(float(min[0]), float(min[1]), float(min[2]))
        )
        p_max = (
            max if isinstance(max, Point3) else Point3(float(max[0]), float(max[1]), float(max[2]))
        )
        object.__setattr__(self, "min", p_min)
        object.__setattr__(self, "max", p_max)

    @property
    def size(self) -> Point3:
        return Point3(
            self.max.x - self.min.x,
            self.max.y - self.min.y,
            self.max.z - self.min.z,
        )


@dataclass(frozen=True, slots=True)
class ExpectedCylinder:
    """Expected cylinder face geometry in millimeters."""

    point: Point3
    direction: Point3
    radius: float

    def __init__(
        self,
        point: Point3 | tuple[float, float, float] | list[float],
        direction: Point3 | tuple[float, float, float] | list[float],
        radius: float,
    ) -> None:
        p_pt = (
            point
            if isinstance(point, Point3)
            else Point3(float(point[0]), float(point[1]), float(point[2]))
        )
        p_dir = (
            direction
            if isinstance(direction, Point3)
            else Point3(float(direction[0]), float(direction[1]), float(direction[2]))
        )
        object.__setattr__(self, "point", p_pt)
        object.__setattr__(self, "direction", p_dir)
        object.__setattr__(self, "radius", float(radius))

    @property
    def radius_mm(self) -> float:
        return self.radius


@dataclass(frozen=True, slots=True)
class ExpectedFeature:
    """Expected solid feature or sketch node in the part feature tree."""

    node_id: str
    feature_type: str
    native_type: str = ""

    @property
    def type(self) -> str:
        return self.feature_type


@dataclass(frozen=True, slots=True)
class ExpectedGeometry:
    """Expected geometry computed from the Part Feature Graph IR alone (spec 10.2)."""

    solid_body_count: int
    bbox_mm: Box
    volume_mm3: float
    surface_area_mm2: float
    center_of_mass_mm: Point3
    cylinders: tuple[ExpectedCylinder, ...]
    features: tuple[ExpectedFeature, ...]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of a single verification requirement comparison."""

    requirement: str
    measured: JsonValue
    expected: JsonValue
    tolerance: float | None
    status: CheckStatus
    method: str
    reason: str | None = None

    def __post_init__(self) -> None:
        """Only ``not_evaluated`` and ``not_applicable`` carry a reason, and need one (8.9.6)."""
        if self.status == "not_evaluated":
            valid = self.reason in NOT_EVALUATED_REASONS
        elif self.status == "not_applicable":
            valid = bool(self.reason)
        else:
            valid = self.reason is None
        if not valid:
            raise ValueError(f"invalid reason {self.reason!r} for status {self.status!r}")

    @property
    def passed(self) -> bool:
        """True only for ``passed``; no other status counts as passed (ADR-063, ADR-064)."""
        return self.status == "passed"


def _order_curve_segments(curves: list[Line | Arc]) -> list[tuple[Line | Arc, bool]]:
    if not curves:
        return []
    remaining = list(curves)
    first = remaining.pop(0)
    ordered: list[tuple[Line | Arc, bool]] = [(first, True)]
    current = first.end

    tol = 1e-5
    while remaining:
        found_idx = -1
        forward = True
        for idx, seg in enumerate(remaining):
            if math.hypot(seg.start[0] - current[0], seg.start[1] - current[1]) <= tol:
                found_idx = idx
                forward = True
                break
            if math.hypot(seg.end[0] - current[0], seg.end[1] - current[1]) <= tol:
                found_idx = idx
                forward = False
                break

        if found_idx == -1:
            for seg in remaining:
                ordered.append((seg, True))
            break

        seg = remaining.pop(found_idx)
        ordered.append((seg, forward))
        current = seg.end if forward else seg.start

    return ordered


def _order_polygon_vertices(lines: list[Line]) -> tuple[list[tuple[float, float]], float]:  # pyright: ignore[reportUnusedFunction]
    """Order line segments into a closed polygon loop, returning vertices and perimeter."""
    curves: list[Line | Arc] = list(lines)
    ordered = _order_curve_segments(curves)
    vertices: list[tuple[float, float]] = []
    perimeter = 0.0
    for seg, forward in ordered:
        start_pt = seg.start if forward else seg.end
        end_pt = seg.end if forward else seg.start
        vertices.append(start_pt)
        perimeter += math.hypot(end_pt[0] - start_pt[0], end_pt[1] - start_pt[1])
    return vertices, perimeter


_ARC_SWEEP_TOL = 1e-12
_ARC_EXTREMA_TOL = 1e-6


def _arc_signed_sweep(th1: float, th2: float, is_ccw: bool) -> tuple[float, float]:
    sweep = (th2 - th1 if is_ccw else th1 - th2) % (2.0 * math.pi)
    if sweep <= _ARC_SWEEP_TOL:
        sweep += 2.0 * math.pi
    signed_sweep = sweep if is_ccw else -sweep
    return sweep, signed_sweep


def _arc_extrema_and_samples(
    center: tuple[float, float],
    r: float,
    th1: float,
    sweep: float,
    is_ccw: bool,
) -> tuple[list[float], list[float], list[tuple[float, float]]]:
    cx, cy = center
    signed_sweep = sweep if is_ccw else -sweep
    xs: list[float] = []
    ys: list[float] = []
    for k in range(4):
        cand_th = k * 0.5 * math.pi
        delta = (cand_th - th1 if is_ccw else th1 - cand_th) % (2.0 * math.pi)
        if _ARC_EXTREMA_TOL < delta < sweep - _ARC_EXTREMA_TOL:
            xs.append(cx + r * math.cos(cand_th))
            ys.append(cy + r * math.sin(cand_th))
    poly_samples = [
        (
            cx + r * math.cos(th1 + (s / 16.0) * signed_sweep),
            cy + r * math.sin(th1 + (s / 16.0) * signed_sweep),
        )
        for s in range(1, 16)
    ]
    return xs, ys, poly_samples


def _compute_curves_profile(
    curves: list[Line | Arc],
) -> tuple[float, float, float, float, tuple[float, float], tuple[float, float]]:
    ordered = _order_curve_segments(curves)
    perimeter = 0.0
    signed_area = 0.0
    all_x: list[float] = []
    all_y: list[float] = []
    poly_vertices: list[tuple[float, float]] = []

    for seg, forward in ordered:
        p1 = seg.start if forward else seg.end
        p2 = seg.end if forward else seg.start
        all_x.extend([p1[0], p2[0]])
        all_y.extend([p1[1], p2[1]])
        poly_vertices.append(p1)

        if isinstance(seg, Line):
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            perimeter += math.hypot(dx, dy)
            signed_area += 0.5 * (p1[0] * p2[1] - p2[0] * p1[1])
        else:
            cx, cy = seg.center
            r = math.hypot(seg.start[0] - cx, seg.start[1] - cy)
            th1 = math.atan2(p1[1] - cy, p1[0] - cx)
            th2 = math.atan2(p2[1] - cy, p2[0] - cx)
            is_ccw = (seg.direction == "ccw") if forward else (seg.direction != "ccw")
            sweep, signed_sweep = _arc_signed_sweep(th1, th2, is_ccw)

            perimeter += r * sweep
            signed_area += 0.5 * (
                r * r * signed_sweep + cx * (p2[1] - p1[1]) - cy * (p2[0] - p1[0])
            )
            arc_xs, arc_ys, samples = _arc_extrema_and_samples(seg.center, r, th1, sweep, is_ccw)
            all_x.extend(arc_xs)
            all_y.extend(arc_ys)
            poly_vertices.extend(samples)

    area = abs(signed_area)

    m = len(poly_vertices)
    poly_signed_area = 0.0
    cx_num = 0.0
    cy_num = 0.0
    for i in range(m):
        x_i, y_i = poly_vertices[i]
        x_next, y_next = poly_vertices[(i + 1) % m]
        cross = x_i * y_next - x_next * y_i
        poly_signed_area += cross
        cx_num += (x_i + x_next) * cross
        cy_num += (y_i + y_next) * cross
    poly_signed_area *= 0.5
    cx = cx_num / (6.0 * poly_signed_area) if poly_signed_area != 0.0 else 0.0
    cy = cy_num / (6.0 * poly_signed_area) if poly_signed_area != 0.0 else 0.0

    return area, perimeter, cx, cy, (min(all_x), max(all_x)), (min(all_y), max(all_y))


def _collect_features(
    graph: PartGraph,
) -> tuple[list[ExpectedFeature], list[tuple[str, SolidNode]]]:
    """Extract ordered expected features and solid nodes from the graph."""
    features: list[ExpectedFeature] = []
    solid_nodes: list[tuple[str, SolidNode]] = []

    for nid, node in graph.nodes.items():
        if isinstance(node, SketchNode):
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="sketch",
                    native_type="ProfileFeature",
                )
            )
        elif isinstance(node, SolidNode):
            solid_nodes.append((nid, node))
            if node.type == "extrude":
                features.append(
                    ExpectedFeature(
                        node_id=nid,
                        feature_type="extrude",
                        native_type="Extrusion",
                    )
                )
            elif node.type == "cut_extrude":
                features.append(
                    ExpectedFeature(
                        node_id=nid,
                        feature_type="cut_extrude",
                        native_type="ICE",
                    )
                )
            else:
                features.append(
                    ExpectedFeature(
                        node_id=nid,
                        feature_type=node.type,
                        native_type="",
                    )
                )
        elif isinstance(node, LinearPattern):
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="linear_pattern",
                    native_type="LPattern",
                )
            )
        elif isinstance(node, CircularPattern):
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="circular_pattern",
                    native_type="CirPattern",
                )
            )
        elif isinstance(node, Mirror):
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="mirror",
                    native_type="MirrorPattern",
                )
            )
        elif isinstance(node, Revolve):
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="revolve",
                    native_type="Revolution",
                )
            )
        else:
            features.append(
                ExpectedFeature(
                    node_id=nid,
                    feature_type="cut_revolve",
                    native_type="RevCut",
                )
            )
    return features, solid_nodes


def _rect_to_bounds_and_metrics(
    r: CornerRectangle | CenterRectangle,
) -> tuple[float, float, float, float, tuple[float, float], tuple[float, float]]:
    """Compute (area, perimeter, cx, cy, (min_x, max_x), (min_y, max_y)) for a rectangle."""
    if isinstance(r, CornerRectangle):
        x_min = min(r.corner1[0], r.corner2[0])
        x_max = max(r.corner1[0], r.corner2[0])
        y_min = min(r.corner1[1], r.corner2[1])
        y_max = max(r.corner1[1], r.corner2[1])
        w = x_max - x_min
        h = y_max - y_min
        cx = (x_min + x_max) * 0.5
        cy = (y_min + y_max) * 0.5
    else:
        w = r.width
        h = r.height
        cx, cy = r.center
        x_min = cx - w * 0.5
        x_max = cx + w * 0.5
        y_min = cy - h * 0.5
        y_max = cy + h * 0.5
    area = w * h
    perimeter = 2.0 * (w + h)
    return area, perimeter, cx, cy, (x_min, x_max), (y_min, y_max)


def _slot_to_bounds_and_metrics(
    s: StraightSlot,
) -> tuple[float, float, float, float, tuple[float, float], tuple[float, float]]:
    """Compute (area, perimeter, cx, cy, (min_x, max_x), (min_y, max_y)) for a straight slot."""
    p1 = s.start_point
    p2 = s.end_point
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    r = s.width * 0.5
    area = length * s.width + math.pi * r * r
    perimeter = 2.0 * length + 2.0 * math.pi * r
    cx = (p1[0] + p2[0]) * 0.5
    cy = (p1[1] + p2[1]) * 0.5
    x_min = min(p1[0], p2[0]) - r
    x_max = max(p1[0], p2[0]) + r
    y_min = min(p1[1], p2[1]) - r
    y_max = max(p1[1], p2[1]) + r
    return area, perimeter, cx, cy, (x_min, x_max), (y_min, y_max)


def _compute_base_profile(
    sketch: SketchNode,
) -> tuple[float, float, float, float, tuple[float, float], tuple[float, float]]:
    """Compute base 2D profile area, perimeter, centroid (cx, cy) and bounds (xs, ys)."""
    curves = [e for e in sketch.entities.values() if isinstance(e, (Line, Arc))]
    circles = [e for e in sketch.entities.values() if isinstance(e, Circle)]
    rectangles = [
        e for e in sketch.entities.values() if isinstance(e, (CornerRectangle, CenterRectangle))
    ]
    slots = [e for e in sketch.entities.values() if isinstance(e, StraightSlot)]

    if curves:
        return _compute_curves_profile(curves)

    if circles:
        c = circles[0]
        r = c.diameter * 0.5
        area = math.pi * r * r
        perimeter = 2.0 * math.pi * r
        cx, cy = c.center
        return area, perimeter, cx, cy, (cx - r, cx + r), (cy - r, cy + r)

    if rectangles:
        return _rect_to_bounds_and_metrics(rectangles[0])

    if slots:
        return _slot_to_bounds_and_metrics(slots[0])

    raise ValueError("Base sketch has no Line, Arc, Circle, Rectangle or Slot entities")


def _cut_regions(sketch: SketchNode) -> list[tuple[float, float, float, float]]:
    """Area, perimeter and centroid of each region a cut removes: one loop, or each circle."""
    circles = [e for e in sketch.entities.values() if isinstance(e, Circle)]
    if circles:
        return [
            (
                math.pi * (c.diameter * 0.5) ** 2,
                math.pi * c.diameter,
                c.center[0],
                c.center[1],
            )
            for c in circles
        ]
    rectangles = [
        e for e in sketch.entities.values() if isinstance(e, (CornerRectangle, CenterRectangle))
    ]
    if rectangles:
        return [
            (metrics[0], metrics[1], metrics[2], metrics[3])
            for metrics in (_rect_to_bounds_and_metrics(r) for r in rectangles)
        ]
    slots = [e for e in sketch.entities.values() if isinstance(e, StraightSlot)]
    if slots:
        return [
            (metrics[0], metrics[1], metrics[2], metrics[3])
            for metrics in (_slot_to_bounds_and_metrics(s) for s in slots)
        ]
    area, perimeter, center_x, center_y, _, _ = _compute_base_profile(sketch)
    return [(area, perimeter, center_x, center_y)]


def _compute_base_bbox(
    base_plane: PlaneAxes,
    x_bounds: tuple[float, float],
    y_bounds: tuple[float, float],
    depth: float,
) -> Box:
    """Compute axis-aligned 3D bounding box for an extruded base profile."""
    corners_2d = [
        (x_bounds[0], y_bounds[0]),
        (x_bounds[1], y_bounds[0]),
        (x_bounds[1], y_bounds[1]),
        (x_bounds[0], y_bounds[1]),
    ]
    corners_3d: list[tuple[float, float, float]] = []
    for cx, cy in corners_2d:
        corners_3d.append(base_plane.to_model(cx, cy, 0.0))
        corners_3d.append(base_plane.to_model(cx, cy, depth))

    min_pt = Point3(
        min(p[0] for p in corners_3d),
        min(p[1] for p in corners_3d),
        min(p[2] for p in corners_3d),
    )
    max_pt = Point3(
        max(p[0] for p in corners_3d),
        max(p[1] for p in corners_3d),
        max(p[2] for p in corners_3d),
    )
    return Box(min=min_pt, max=max_pt)


def _cut_frame_and_depths(
    plane_name: str,
    base_plane: PlaneAxes,
    base_depth: float,
    cut_depth: float,
) -> tuple[PlaneAxes | FaceFrame, float, float, tuple[float, float, float]]:
    """Return (projector, depth_center, circle_depth, cyl_dir) for a cut sketch."""
    face = parse_face_plane(plane_name)
    if face is None:
        cut_plane = plane_axes(plane_name)
        return cut_plane, cut_depth * 0.5, 0.0, cut_plane.normal
    # A cut from a cap face goes into the body (ADR-070); its x may be mirrored.
    frame = face_frame(base_plane, base_depth, face.role)
    low, high = frame.into_body_depth_from_base(base_depth, cut_depth)
    return frame, (low + high) * 0.5, frame.offset_mm, frame.base_normal


def _collect_base_cylinders(
    base_sketch: SketchNode, base_plane: PlaneAxes, base_cx: float, base_cy: float
) -> list[ExpectedCylinder]:
    cylinders: list[ExpectedCylinder] = []
    base_circles = [e for e in base_sketch.entities.values() if isinstance(e, Circle)]
    if base_circles:
        cylinders.append(
            ExpectedCylinder(
                point=base_plane.to_model(base_cx, base_cy, 0.0),
                direction=base_plane.normal,
                radius=base_circles[0].diameter * 0.5,
            )
        )
    for arc in [e for e in base_sketch.entities.values() if isinstance(e, Arc)]:
        r = math.hypot(arc.start[0] - arc.center[0], arc.start[1] - arc.center[1])
        cylinders.append(
            ExpectedCylinder(
                point=base_plane.to_model(arc.center[0], arc.center[1], 0.0),
                direction=base_plane.normal,
                radius=r,
            )
        )
    for slot in [e for e in base_sketch.entities.values() if isinstance(e, StraightSlot)]:
        r = slot.width * 0.5
        cylinders.append(
            ExpectedCylinder(
                point=base_plane.to_model(slot.start_point[0], slot.start_point[1], 0.0),
                direction=base_plane.normal,
                radius=r,
            )
        )
        cylinders.append(
            ExpectedCylinder(
                point=base_plane.to_model(slot.end_point[0], slot.end_point[1], 0.0),
                direction=base_plane.normal,
                radius=r,
            )
        )
    return cylinders


def _collect_cut_entity_cylinders(
    cut_sketch: SketchNode,
    projector: PlaneAxes | FaceFrame,
    circle_depth: float,
    cyl_dir: tuple[float, float, float],
) -> list[ExpectedCylinder]:
    cylinders: list[ExpectedCylinder] = []
    for entity in cut_sketch.entities.values():
        if isinstance(entity, Circle):
            cylinders.append(
                ExpectedCylinder(
                    point=projector.to_model(entity.center[0], entity.center[1], circle_depth),
                    direction=cyl_dir,
                    radius=entity.diameter * 0.5,
                )
            )
        elif isinstance(entity, Arc):
            r = math.hypot(entity.start[0] - entity.center[0], entity.start[1] - entity.center[1])
            cylinders.append(
                ExpectedCylinder(
                    point=projector.to_model(entity.center[0], entity.center[1], circle_depth),
                    direction=cyl_dir,
                    radius=r,
                )
            )
        elif isinstance(entity, StraightSlot):
            r = entity.width * 0.5
            cylinders.append(
                ExpectedCylinder(
                    point=projector.to_model(
                        entity.start_point[0], entity.start_point[1], circle_depth
                    ),
                    direction=cyl_dir,
                    radius=r,
                )
            )
            cylinders.append(
                ExpectedCylinder(
                    point=projector.to_model(
                        entity.end_point[0], entity.end_point[1], circle_depth
                    ),
                    direction=cyl_dir,
                    radius=r,
                )
            )
    return cylinders


@dataclass
class _GeometryAccumulator:
    volume: float
    area: float
    moment: list[float]
    cylinders: list[ExpectedCylinder]


def _direction_2d_offset(
    sketch_plane: str, dir_spec: LinearPatternDirection
) -> tuple[float, float] | None:
    try:
        sp_axes = plane_axes(sketch_plane)
    except ValueError:
        return None

    try:
        dp_axes = plane_axes(dir_spec.direction)
        d3 = dp_axes.normal
    except ValueError:
        return None

    du = d3[0] * sp_axes.x_axis[0] + d3[1] * sp_axes.x_axis[1] + d3[2] * sp_axes.x_axis[2]
    dv = d3[0] * sp_axes.y_axis[0] + d3[1] * sp_axes.y_axis[1] + d3[2] * sp_axes.y_axis[2]
    if dir_spec.reverse:
        du = -du
        dv = -dv
    return du, dv


def _apply_pattern_instances(
    pat: LinearPattern,
    graph: PartGraph,
    base_plane: PlaneAxes,
    base_depth: float,
    acc: _GeometryAccumulator,
) -> None:
    for seed_id in pat.seeds:
        seed_node = graph.nodes.get(seed_id)
        if not isinstance(seed_node, SolidNode) or seed_node.type != "cut_extrude":
            continue
        cut_sketch_raw = graph.nodes.get(seed_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue

        off1 = _direction_2d_offset(cut_sketch_raw.plane, pat.direction_1)
        if off1 is None:
            continue
        u1, v1 = off1
        count1 = pat.direction_1.count
        spacing1 = pat.direction_1.spacing

        count2 = pat.direction_2.count if pat.direction_2 is not None else 1
        spacing2 = pat.direction_2.spacing if pat.direction_2 is not None else 0.0
        off2 = (
            _direction_2d_offset(cut_sketch_raw.plane, pat.direction_2)
            if pat.direction_2 is not None
            else None
        )
        u2, v2 = off2 if off2 is not None else (0.0, 0.0)

        is_through = seed_node.end_condition.type in ("through_all", "through_all_both")
        cut_depth = base_depth if is_through else float(seed_node.end_condition.depth or 0.0)
        projector, depth_center, circle_depth, cyl_dir = _cut_frame_and_depths(
            cut_sketch_raw.plane, base_plane, base_depth, cut_depth
        )

        regions = list(_cut_regions(cut_sketch_raw))
        seed_cylinders = _collect_cut_entity_cylinders(
            cut_sketch_raw, projector, circle_depth, cyl_dir
        )
        p0 = projector.to_model(0.0, 0.0, 0.0)

        for k1 in range(count1):
            for k2 in range(count2):
                if k1 == 0 and k2 == 0:
                    continue
                du = k1 * spacing1 * u1 + k2 * spacing2 * u2
                dv = k1 * spacing1 * v1 + k2 * spacing2 * v2

                for area, perimeter, center_x, center_y in regions:
                    region_vol = area * cut_depth
                    region_com = projector.to_model(center_x + du, center_y + dv, depth_center)

                    acc.volume -= region_vol
                    acc.moment[0] -= region_vol * region_com[0]
                    acc.moment[1] -= region_vol * region_com[1]
                    acc.moment[2] -= region_vol * region_com[2]
                    acc.area += perimeter * cut_depth - (2.0 * area if is_through else 0.0)

                pk = projector.to_model(du, dv, 0.0)
                delta_3d = (pk[0] - p0[0], pk[1] - p0[1], pk[2] - p0[2])
                for cyl in seed_cylinders:
                    acc.cylinders.append(
                        ExpectedCylinder(
                            point=Point3(
                                cyl.point.x + delta_3d[0],
                                cyl.point.y + delta_3d[1],
                                cyl.point.z + delta_3d[2],
                            ),
                            direction=cyl.direction,
                            radius=cyl.radius,
                        )
                    )


def _apply_circular_pattern_instances(
    pat: CircularPattern,
    graph: PartGraph,
    base_plane: PlaneAxes,
    base_depth: float,
    acc: _GeometryAccumulator,
) -> None:
    for seed_id in pat.seeds:
        seed_node = graph.nodes.get(seed_id)
        if not isinstance(seed_node, SolidNode) or seed_node.type != "cut_extrude":
            continue
        cut_sketch_raw = graph.nodes.get(seed_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue

        count = pat.count
        if count < MIN_PATTERN_COUNT:
            continue

        step_angle = (
            math.radians(pat.spacing) / count if pat.equal_spacing else math.radians(pat.spacing)
        )
        if pat.reverse:
            step_angle = -step_angle

        is_through = seed_node.end_condition.type in ("through_all", "through_all_both")
        cut_depth = base_depth if is_through else float(seed_node.end_condition.depth or 0.0)
        projector, depth_center, circle_depth, cyl_dir = _cut_frame_and_depths(
            cut_sketch_raw.plane, base_plane, base_depth, cut_depth
        )

        regions = list(_cut_regions(cut_sketch_raw))
        seed_cylinders = _collect_cut_entity_cylinders(
            cut_sketch_raw, projector, circle_depth, cyl_dir
        )

        for k in range(1, count):
            theta = k * step_angle
            cos_th = math.cos(theta)
            sin_th = math.sin(theta)

            for area, perimeter, center_x, center_y in regions:
                region_vol = area * cut_depth
                rx = center_x * cos_th - center_y * sin_th
                ry = center_x * sin_th + center_y * cos_th
                region_com = projector.to_model(rx, ry, depth_center)

                acc.volume -= region_vol
                acc.moment[0] -= region_vol * region_com[0]
                acc.moment[1] -= region_vol * region_com[1]
                acc.moment[2] -= region_vol * region_com[2]
                acc.area += perimeter * cut_depth - (2.0 * area if is_through else 0.0)

            for cyl in seed_cylinders:
                cx = cyl.point.x * cos_th - cyl.point.y * sin_th
                cy = cyl.point.x * sin_th + cyl.point.y * cos_th
                acc.cylinders.append(
                    ExpectedCylinder(
                        point=Point3(cx, cy, cyl.point.z),
                        direction=cyl.direction,
                        radius=cyl.radius,
                    )
                )


def _mirror_plane_origin_and_normal(
    plane_name: str,
    base_plane: PlaneAxes,
    base_depth: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    face = parse_face_plane(plane_name)
    if face is None:
        p_axes = plane_axes(plane_name)
        return (0.0, 0.0, 0.0), p_axes.normal
    frame = face_frame(base_plane, base_depth, face.role)
    origin = (
        frame.base_normal[0] * frame.offset_mm,
        frame.base_normal[1] * frame.offset_mm,
        frame.base_normal[2] * frame.offset_mm,
    )
    return origin, frame.base_normal


def _apply_mirror_instances(
    mir: Mirror,
    graph: PartGraph,
    base_plane: PlaneAxes,
    base_depth: float,
    acc: _GeometryAccumulator,
) -> None:
    p0, normal = _mirror_plane_origin_and_normal(mir.plane, base_plane, base_depth)
    nx, ny, nz = normal
    p0x, p0y, p0z = p0

    def reflect_point(pt: tuple[float, float, float]) -> tuple[float, float, float]:
        vx, vy, vz = pt[0] - p0x, pt[1] - p0y, pt[2] - p0z
        dist = vx * nx + vy * ny + vz * nz
        return (pt[0] - 2.0 * dist * nx, pt[1] - 2.0 * dist * ny, pt[2] - 2.0 * dist * nz)

    def reflect_dir(d: tuple[float, float, float]) -> tuple[float, float, float]:
        dot = d[0] * nx + d[1] * ny + d[2] * nz
        return (d[0] - 2.0 * dot * nx, d[1] - 2.0 * dot * ny, d[2] - 2.0 * dot * nz)

    for seed_id in mir.seeds:
        seed_node = graph.nodes.get(seed_id)
        if not isinstance(seed_node, SolidNode) or seed_node.type != "cut_extrude":
            continue
        cut_sketch_raw = graph.nodes.get(seed_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue

        is_through = seed_node.end_condition.type in ("through_all", "through_all_both")
        cut_depth = base_depth if is_through else float(seed_node.end_condition.depth or 0.0)
        projector, depth_center, circle_depth, cyl_dir = _cut_frame_and_depths(
            cut_sketch_raw.plane, base_plane, base_depth, cut_depth
        )

        regions = list(_cut_regions(cut_sketch_raw))
        seed_cylinders = _collect_cut_entity_cylinders(
            cut_sketch_raw, projector, circle_depth, cyl_dir
        )

        for area, perimeter, center_x, center_y in regions:
            region_vol = area * cut_depth
            seed_com = projector.to_model(center_x, center_y, depth_center)
            mir_com = reflect_point(seed_com)

            acc.volume -= region_vol
            acc.moment[0] -= region_vol * mir_com[0]
            acc.moment[1] -= region_vol * mir_com[1]
            acc.moment[2] -= region_vol * mir_com[2]
            acc.area += perimeter * cut_depth - (2.0 * area if is_through else 0.0)

        for cyl in seed_cylinders:
            cp = reflect_point((cyl.point.x, cyl.point.y, cyl.point.z))
            cd = reflect_dir(cyl.direction)
            acc.cylinders.append(
                ExpectedCylinder(
                    point=Point3(cp[0], cp[1], cp[2]),
                    direction=cd,
                    radius=cyl.radius,
                )
            )


def _compute_revolve_profile(
    sketch: SketchNode,
    axis_ref: str | None,
    angle_deg: float,
    *,
    is_cut: bool = False,
) -> tuple[float, Point3, list[ExpectedCylinder], tuple[float, float, float, float]]:
    """Compute volume, centroid, cylinders, and bounds for a revolve profile (Pappus Theorem)."""
    plane = plane_axes(sketch.plane)

    # 1. Determine axis position u_axis (default 0.0)
    u_axis = 0.0
    for ent in sketch.entities.values():
        if (
            isinstance(ent, Line)
            and getattr(ent, "construction", False)
            and abs(ent.start[0] - ent.end[0]) < REVOLVE_AXIS_TOL
        ):
            u_axis = ent.start[0]
            break

    # 2. Extract outline lines
    lines = [
        e
        for e in sketch.entities.values()
        if isinstance(e, Line) and not getattr(e, "construction", False)
    ]
    if not lines:
        raise ValueError("Sketch contains no outline lines for revolve")

    vertices, _ = _order_polygon_vertices(lines)
    n = len(vertices)

    area_signed = 0.0
    c_u_sum = 0.0
    c_v_sum = 0.0
    v_min = float("inf")
    v_max = float("-inf")
    r_max = 0.0

    for i in range(n):
        u_i, v_i = vertices[i]
        u_next, v_next = vertices[(i + 1) % n]
        cross = u_i * v_next - u_next * v_i
        area_signed += cross
        c_u_sum += (u_i + u_next) * cross
        c_v_sum += (v_i + v_next) * cross

        r_max = max(r_max, abs(u_i - u_axis))
        v_min = min(v_min, v_i)
        v_max = max(v_max, v_i)

    area_2d = 0.5 * abs(area_signed)
    if area_2d < REVOLVE_AREA_TOL:
        raise ValueError("Revolve profile polygon has zero area")

    denom = 6.0 * (0.5 * area_signed)
    c_u = c_u_sum / denom
    c_v = c_v_sum / denom

    r_centroid = abs(c_u - u_axis)
    theta_rad = math.radians(angle_deg)
    vol = theta_rad * r_centroid * area_2d

    com_3d_tuple = plane.to_model(u_axis, c_v, 0.0)
    com_3d = Point3(com_3d_tuple[0], com_3d_tuple[1], com_3d_tuple[2])

    # 3. Cylinders from lines parallel to axis
    cylinders: list[ExpectedCylinder] = []
    p0 = plane.to_model(u_axis, 0.0, 0.0)
    p1 = plane.to_model(u_axis, 1.0, 0.0)
    axis_dir = Point3(p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])

    for line in lines:
        if abs(line.start[0] - line.end[0]) < REVOLVE_PARALLEL_TOL:
            radius = abs(line.start[0] - u_axis)
            if radius > REVOLVE_RADIUS_TOL:
                if is_cut and radius >= r_max - REVOLVE_RADIUS_TOL:
                    continue
                mid_v = (line.start[1] + line.end[1]) * 0.5
                c_pt = plane.to_model(u_axis, mid_v, 0.0)
                cylinders.append(
                    ExpectedCylinder(
                        point=Point3(c_pt[0], c_pt[1], c_pt[2]),
                        direction=axis_dir,
                        radius=radius,
                    )
                )

    return vol, com_3d, cylinders, (r_max, v_min, v_max, u_axis)


def _expected_geometry_revolve(
    graph: PartGraph,
    features: Sequence[ExpectedFeature],
    revolve_entries: Sequence[tuple[str, Revolve]],
) -> ExpectedGeometry:
    """Compute expected geometry for a revolved part."""
    _, base_node = revolve_entries[0]
    base_sketch_raw = graph.nodes.get(base_node.profile)
    if not isinstance(base_sketch_raw, SketchNode):
        raise ValueError(f"Profile {base_node.profile!r} is not a SketchNode")

    base_vol, base_com, base_cylinders, bounds = _compute_revolve_profile(
        base_sketch_raw, base_node.axis, base_node.angle
    )
    r_max, v_min, v_max, _ = bounds

    p_min = Point3(-r_max, v_min, -r_max)
    p_max = Point3(r_max, v_max, r_max)
    bbox_mm = Box(min=p_min, max=p_max)

    total_volume = base_vol
    total_moment = [base_vol * base_com.x, base_vol * base_com.y, base_vol * base_com.z]
    total_area = 2.0 * math.pi * r_max * (v_max - v_min) + 2.0 * math.pi * r_max**2
    cylinders = list(base_cylinders)

    cut_revolve_entries = [(nid, n) for nid, n in graph.nodes.items() if isinstance(n, CutRevolve)]
    for _, cut_node in cut_revolve_entries:
        cut_sketch_raw = graph.nodes.get(cut_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue
        cut_vol, cut_com, cut_cyls, cut_bounds = _compute_revolve_profile(
            cut_sketch_raw, cut_node.axis, cut_node.angle, is_cut=True
        )
        total_volume -= cut_vol
        total_moment[0] -= cut_vol * cut_com.x
        total_moment[1] -= cut_vol * cut_com.y
        total_moment[2] -= cut_vol * cut_com.z

        cut_r_max, cut_v_min, cut_v_max, _ = cut_bounds
        cut_height = cut_v_max - cut_v_min
        floor_r = cut_cyls[0].radius if cut_cyls else 0.0

        total_area += (
            2.0 * math.pi * floor_r * cut_height
            - 2.0 * math.pi * cut_r_max * cut_height
            + 2.0 * math.pi * (cut_r_max**2 - floor_r**2)
        )

        if (
            cut_v_min > v_min + REVOLVE_RADIUS_TOL
            and cut_v_max < v_max - REVOLVE_RADIUS_TOL
            and base_cylinders
        ):
            cylinders.append(base_cylinders[0])
        cylinders.extend(cut_cyls)

    com_3d = Point3(
        total_moment[0] / total_volume,
        total_moment[1] / total_volume,
        total_moment[2] / total_volume,
    )

    return ExpectedGeometry(
        solid_body_count=1,
        bbox_mm=bbox_mm,
        volume_mm3=total_volume,
        surface_area_mm2=total_area,
        center_of_mass_mm=com_3d,
        cylinders=tuple(cylinders),
        features=tuple(features),
    )


def expected_geometry(graph: PartGraph) -> ExpectedGeometry:
    """Compute expected geometry from a PartGraph alone (spec 10.2, design 9)."""
    features, solid_nodes = _collect_features(graph)

    extrude_entries = [e for e in solid_nodes if e[1].type == "extrude"]
    revolve_entries = [(nid, n) for nid, n in graph.nodes.items() if isinstance(n, Revolve)]

    if not extrude_entries and not revolve_entries:
        raise ValueError("PartGraph has no solid base feature (extrude or revolve)")

    if revolve_entries:
        return _expected_geometry_revolve(graph, features, revolve_entries)

    _, base_node = extrude_entries[0]
    base_sketch_raw = graph.nodes.get(base_node.profile)
    if not isinstance(base_sketch_raw, SketchNode):
        raise ValueError(f"Profile {base_node.profile!r} is not a SketchNode")

    base_plane = plane_axes(base_sketch_raw.plane)
    base_depth = float(base_node.end_condition.depth or 0.0)

    base_area, base_perimeter, base_cx, base_cy, x_b, y_b = _compute_base_profile(base_sketch_raw)
    bbox_mm = _compute_base_bbox(base_plane, x_b, y_b, base_depth)

    base_vol = base_area * base_depth
    base_com = base_plane.to_model(base_cx, base_cy, base_depth * 0.5)
    total_moment = [base_vol * base_com[0], base_vol * base_com[1], base_vol * base_com[2]]
    total_volume = base_vol
    total_area = 2.0 * base_area + base_perimeter * base_depth

    cylinders = _collect_base_cylinders(base_sketch_raw, base_plane, base_cx, base_cy)

    cut_entries = [e for e in solid_nodes if e[1].type == "cut_extrude"]
    for _, cut_node in cut_entries:
        cut_sketch_raw = graph.nodes.get(cut_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue

        is_through = cut_node.end_condition.type in ("through_all", "through_all_both")
        cut_depth = base_depth if is_through else float(cut_node.end_condition.depth or 0.0)
        projector, depth_center, circle_depth, cyl_dir = _cut_frame_and_depths(
            cut_sketch_raw.plane, base_plane, base_depth, cut_depth
        )

        for area, perimeter, center_x, center_y in _cut_regions(cut_sketch_raw):
            region_vol = area * cut_depth
            region_com = projector.to_model(center_x, center_y, depth_center)

            total_volume -= region_vol
            total_moment[0] -= region_vol * region_com[0]
            total_moment[1] -= region_vol * region_com[1]
            total_moment[2] -= region_vol * region_com[2]

            # A through cut opens both end faces. A blind cut's floor replaces the area it removes.
            total_area += perimeter * cut_depth - (2.0 * area if is_through else 0.0)

        cylinders.extend(
            _collect_cut_entity_cylinders(cut_sketch_raw, projector, circle_depth, cyl_dir)
        )

    acc = _GeometryAccumulator(
        volume=total_volume,
        area=total_area,
        moment=total_moment,
        cylinders=cylinders,
    )
    for pat in [n for n in graph.nodes.values() if isinstance(n, LinearPattern)]:
        _apply_pattern_instances(pat, graph, base_plane, base_depth, acc)
    for pat in [n for n in graph.nodes.values() if isinstance(n, CircularPattern)]:
        _apply_circular_pattern_instances(pat, graph, base_plane, base_depth, acc)
    for mir in [n for n in graph.nodes.values() if isinstance(n, Mirror)]:
        _apply_mirror_instances(mir, graph, base_plane, base_depth, acc)

    total_volume = acc.volume
    total_area = acc.area

    com_3d = Point3(
        acc.moment[0] / total_volume,
        acc.moment[1] / total_volume,
        acc.moment[2] / total_volume,
    )

    return ExpectedGeometry(
        solid_body_count=1,
        bbox_mm=bbox_mm,
        volume_mm3=total_volume,
        surface_area_mm2=total_area,
        center_of_mass_mm=com_3d,
        cylinders=tuple(cylinders),
        features=tuple(features),
    )


def _cylinder_matches(
    exp: ExpectedCylinder,
    meas: tuple[tuple[float, float, float], tuple[float, float, float], float],
) -> bool:
    """Check if a measured cylinder matches an expected cylinder within tolerances."""
    meas_pt, meas_dir, meas_r = meas

    if abs(meas_r - exp.radius) > LINEAR_TOLERANCE_MM + 1e-9:
        return False

    norm_m = math.hypot(meas_dir[0], meas_dir[1], meas_dir[2])
    norm_e = math.hypot(exp.direction.x, exp.direction.y, exp.direction.z)
    if norm_m == 0.0 or norm_e == 0.0:
        return False

    dir_m = (meas_dir[0] / norm_m, meas_dir[1] / norm_m, meas_dir[2] / norm_m)
    dir_e = (exp.direction.x / norm_e, exp.direction.y / norm_e, exp.direction.z / norm_e)

    dot = abs(dir_m[0] * dir_e[0] + dir_m[1] * dir_e[1] + dir_m[2] * dir_e[2])
    if 1.0 - dot > PARALLEL_DOT_TOLERANCE:
        return False

    vx = meas_pt[0] - exp.point.x
    vy = meas_pt[1] - exp.point.y
    vz = meas_pt[2] - exp.point.z

    proj = vx * dir_e[0] + vy * dir_e[1] + vz * dir_e[2]
    perp_x = vx - proj * dir_e[0]
    perp_y = vy - proj * dir_e[1]
    perp_z = vz - proj * dir_e[2]

    perp_dist = math.hypot(perp_x, perp_y, perp_z)
    return perp_dist <= LINEAR_TOLERANCE_MM + 1e-9


def _match_cylinders(
    expected: tuple[ExpectedCylinder, ...],
    measured: list[tuple[tuple[float, float, float], tuple[float, float, float], float]],
) -> bool:
    """Find a 1-to-1 matching between expected and measured cylinders via bipartite matching."""
    if len(expected) != len(measured):
        return False
    n = len(expected)
    if n == 0:
        return True

    adj: list[list[int]] = []
    for exp in expected:
        matches = [j for j, m in enumerate(measured) if _cylinder_matches(exp, m)]
        adj.append(matches)

    match_to_exp = [-1] * n

    def dfs(u: int, visited: list[bool]) -> bool:
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True
                if match_to_exp[v] < 0 or dfs(match_to_exp[v], visited):
                    match_to_exp[v] = u
                    return True
        return False

    matches_count = 0
    for u in range(n):
        visited = [False] * n
        if dfs(u, visited):
            matches_count += 1

    return matches_count == n


class _UnreadableError(Exception):
    """A measured value is absent or malformed, so its check cannot be judged."""

    def __init__(self, reason: UnreadableReason) -> None:
        super().__init__(reason)
        self.reason: UnreadableReason = reason


type _Measured = Mapping[str, JsonValue]
type _Judgement = tuple[JsonValue, bool]
type _MeasuredCylinder = tuple[tuple[float, float, float], tuple[float, float, float], float]


def _field(m_dict: _Measured, key: str) -> JsonValue:
    if key not in m_dict:
        raise _UnreadableError("missing_data")
    return m_dict[key]


def _member(entry: _Measured, key: str) -> JsonValue:
    """A key inside a field that is present; its absence makes that field malformed."""
    if key not in entry:
        raise _UnreadableError("malformed_data")
    return entry[key]


def _as_mapping(value: JsonValue) -> _Measured:
    if not isinstance(value, Mapping):
        raise _UnreadableError("malformed_data")
    return cast(_Measured, value)


def _as_list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise _UnreadableError("malformed_data")
    return value


def _as_number(value: JsonValue) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise _UnreadableError("malformed_data")
    return float(value)


def _as_vector(value: JsonValue) -> tuple[float, float, float]:
    items = _as_list(value)
    if len(items) != DIM_3D:
        raise _UnreadableError("malformed_data")
    return (_as_number(items[0]), _as_number(items[1]), _as_number(items[2]))


def _judge_rebuild(m_dict: _Measured) -> _Judgement:
    rebuild = _as_mapping(_field(m_dict, "rebuild"))
    ok = _member(rebuild, "ok")
    if not isinstance(ok, bool):
        raise _UnreadableError("malformed_data")
    errors = [str(e) for e in _as_list(_member(rebuild, "errors"))]
    measured: JsonValue = {"ok": ok, "errors": [cast(JsonValue, e) for e in errors]}
    return measured, ok and not errors


def _judge_bodies(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    count = _field(m_dict, "solid_body_count")
    if isinstance(count, bool) or not isinstance(count, int):
        raise _UnreadableError("malformed_data")
    return count, count == expected.solid_body_count


# Every new part holds these before any feature is built: the tree's folders, the three reference
# planes and the origin (spike section 3). They are the template's, not the plan's, so they are
# neither expected nor "extra". Any other type that the plan does not name still fails.
_TEMPLATE_TREE_TYPES: Final = frozenset({"RefPlane", "OriginProfileFeature", "DetailCabinet"})


def _is_template_tree(feature_type: str) -> bool:
    return feature_type in _TEMPLATE_TREE_TYPES or feature_type.endswith("Folder")


def _is_acceptable_feature_type(exp_feat: ExpectedFeature, meas_type: str) -> bool:
    """Check if the measured feature type string is acceptable for the expected feature."""
    acceptable: set[str] = {exp_feat.feature_type, exp_feat.native_type}
    if exp_feat.feature_type == "sketch":
        acceptable.update(["sketch", "ProfileFeature"])
    elif exp_feat.feature_type == "extrude":
        acceptable.update(["extrude", "Extrusion", "Boss-Extrude"])
    elif exp_feat.feature_type == "cut_extrude":
        acceptable.update(["cut_extrude", "ICE", "Cut-Extrude", "CutExtrude"])
    return meas_type in acceptable


def _read_feature(value: JsonValue) -> tuple[str, str, str]:
    entry = _as_mapping(value)
    feature_id, feature_type, status = (
        entry.get("feature_id"),
        entry.get("type"),
        entry.get("status"),
    )
    if (
        not isinstance(feature_id, str)
        or not isinstance(feature_type, str)
        or not isinstance(status, str)
    ):
        raise _UnreadableError("malformed_data")
    return feature_id, feature_type, status


def _judge_features(
    m_dict: _Measured, expected: ExpectedGeometry, feature_ids: Mapping[str, str]
) -> _Judgement:
    measured = [
        feature
        for feature in (_read_feature(f) for f in _as_list(_field(m_dict, "features")))
        if not _is_template_tree(feature[1])
    ]
    by_id = {feature_id: (kind, status) for feature_id, kind, status in measured}
    passed = len(measured) == len(expected.features)

    for exp_feat in expected.features:
        found = by_id.get(feature_ids.get(exp_feat.node_id, ""))
        if found is None or found[1] != "ok" or not _is_acceptable_feature_type(exp_feat, found[0]):
            passed = False

    bound = {feature_ids[ef.node_id] for ef in expected.features if ef.node_id in feature_ids}
    if any(feature_id not in bound for feature_id in by_id):
        passed = False
    return len(measured), passed


def _within_linear(measured: Sequence[float], expected: Sequence[float]) -> bool:
    return all(
        abs(m - e) <= LINEAR_TOLERANCE_MM + 1e-9 for m, e in zip(measured, expected, strict=True)
    )


def _judge_bbox(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    bbox = _as_mapping(_field(m_dict, "bbox_m"))
    meas_min = [x * MM_PER_M for x in _as_vector(_member(bbox, "min"))]
    meas_max = [x * MM_PER_M for x in _as_vector(_member(bbox, "max"))]
    passed = _within_linear(meas_min, expected.bbox_mm.min) and _within_linear(
        meas_max, expected.bbox_mm.max
    )
    measured: JsonValue = {
        "min": [cast(JsonValue, x) for x in meas_min],
        "max": [cast(JsonValue, x) for x in meas_max],
    }
    return measured, passed


def _within_relative(measured: float, expected: float) -> bool:
    return abs(measured - expected) <= RELATIVE_TOLERANCE_RATIO * expected + 1e-9


def _judge_volume(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    measured = _as_number(_field(m_dict, "volume_m3")) * MM3_PER_M3
    return measured, _within_relative(measured, expected.volume_mm3)


def _judge_surface_area(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    measured = _as_number(_field(m_dict, "surface_area_m2")) * MM2_PER_M2
    return measured, _within_relative(measured, expected.surface_area_mm2)


def _judge_center_of_mass(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    measured = [x * MM_PER_M for x in _as_vector(_field(m_dict, "center_of_mass_m"))]
    passed = _within_linear(measured, expected.center_of_mass_mm)
    return [cast(JsonValue, x) for x in measured], passed


def _read_cylinder(value: JsonValue) -> _MeasuredCylinder:
    entry = _as_mapping(value)
    point = _as_vector(_member(entry, "point"))
    direction = _as_vector(_member(entry, "direction"))
    radius = _as_number(_member(entry, "radius"))
    return (
        (point[0] * MM_PER_M, point[1] * MM_PER_M, point[2] * MM_PER_M),
        direction,
        radius * MM_PER_M,
    )


def _judge_cylinders(m_dict: _Measured, expected: ExpectedGeometry) -> _Judgement:
    measured = [_read_cylinder(c) for c in _as_list(_field(m_dict, "cylinders_m"))]
    return len(measured), _match_cylinders(expected.cylinders, measured)


def _result(
    spec: tuple[str, str, float | None],
    expected: JsonValue,
    judge: Callable[[], _Judgement],
) -> CheckResult:
    requirement, method, tolerance = spec
    try:
        measured, passed = judge()
    except _UnreadableError as unreadable:
        return CheckResult(
            requirement=requirement,
            measured=None,
            expected=expected,
            tolerance=tolerance,
            status="not_evaluated",
            method=method,
            reason=unreadable.reason,
        )
    return CheckResult(
        requirement=requirement,
        measured=measured,
        expected=expected,
        tolerance=tolerance,
        status="passed" if passed else "failed",
        method=method,
    )


def compare(
    expected: ExpectedGeometry,
    measured: JsonValue,
    feature_ids: Mapping[str, str],
) -> tuple[CheckResult, ...]:
    """Compare expected geometry against raw SI measurements from SOLIDWORKS (spec 10.2).

    Converts raw SI values (m, m2, m3) to mm, mm2, mm3 before checking. Never short-circuits:
    runs every comparison and returns all results. A value that is absent or malformed gives
    ``not_evaluated`` with a reason, never ``passed`` (ADR-063, spec 8.9.6).
    """
    m_dict: _Measured = cast(_Measured, measured) if isinstance(measured, Mapping) else {}
    box = expected.bbox_mm
    expected_box: JsonValue = {
        "min": [cast(JsonValue, x) for x in box.min],
        "max": [cast(JsonValue, x) for x in box.max],
    }
    return (
        _result(
            ("rebuild", "part.measure.rebuild", None),
            {"ok": True, "errors": []},
            lambda: _judge_rebuild(m_dict),
        ),
        _result(
            ("bodies", "part.measure.solid_body_count", None),
            expected.solid_body_count,
            lambda: _judge_bodies(m_dict, expected),
        ),
        _result(
            ("features", "part.measure.features", None),
            len(expected.features),
            lambda: _judge_features(m_dict, expected, feature_ids),
        ),
        _result(
            ("bounding_box", "part.measure.bbox", LINEAR_TOLERANCE_MM),
            expected_box,
            lambda: _judge_bbox(m_dict, expected),
        ),
        _result(
            ("volume", "part.measure.volume", RELATIVE_TOLERANCE_RATIO),
            expected.volume_mm3,
            lambda: _judge_volume(m_dict, expected),
        ),
        _result(
            ("surface_area", "part.measure.surface_area", RELATIVE_TOLERANCE_RATIO),
            expected.surface_area_mm2,
            lambda: _judge_surface_area(m_dict, expected),
        ),
        _result(
            ("center_of_mass", "part.measure.center_of_mass", LINEAR_TOLERANCE_MM),
            [cast(JsonValue, x) for x in expected.center_of_mass_mm],
            lambda: _judge_center_of_mass(m_dict, expected),
        ),
        _result(
            ("cylinders", "part.measure.cylinders", LINEAR_TOLERANCE_MM),
            len(expected.cylinders),
            lambda: _judge_cylinders(m_dict, expected),
        ),
    )
