"""CAD part verification core: expected geometry computation and measurement comparison."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple, cast

from cad_ir.core.json_types import JsonValue
from cad_ir.part_feature_graph.model import (
    Circle,
    Line,
    PartGraph,
    SketchNode,
    SolidNode,
)
from cad_ir.part_feature_graph.planes import PlaneAxes, plane_axes

PARALLEL_DOT_TOLERANCE = 1e-4
LINEAR_TOLERANCE_MM = 0.01
RELATIVE_TOLERANCE_RATIO = 0.0001
DIM_3D = 3


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
    passed: bool
    method: str


def _order_polygon_vertices(lines: list[Line]) -> tuple[list[tuple[float, float]], float]:
    """Order line segments into a closed polygon loop, returning vertices and perimeter."""
    if not lines:
        return [], 0.0

    perimeter = 0.0
    for line in lines:
        dx = line.end[0] - line.start[0]
        dy = line.end[1] - line.start[1]
        perimeter += math.hypot(dx, dy)

    remaining = list(lines)
    first = remaining.pop(0)
    vertices = [first.start]
    current = first.end

    tol = 1e-5
    while remaining:
        found_idx = -1
        reverse = False
        for idx, seg in enumerate(remaining):
            if math.hypot(seg.start[0] - current[0], seg.start[1] - current[1]) <= tol:
                found_idx = idx
                reverse = False
                break
            if math.hypot(seg.end[0] - current[0], seg.end[1] - current[1]) <= tol:
                found_idx = idx
                reverse = True
                break

        if found_idx == -1:
            return [line.start for line in lines], perimeter

        seg = remaining.pop(found_idx)
        vertices.append(current)
        current = seg.start if reverse else seg.end

    return vertices, perimeter


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
        else:
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
    return features, solid_nodes


def _compute_base_profile(
    sketch: SketchNode,
) -> tuple[float, float, float, float, tuple[float, float], tuple[float, float]]:
    """Compute base 2D profile area, perimeter, centroid (cx, cy) and bounds (xs, ys)."""
    lines = [e for e in sketch.entities.values() if isinstance(e, Line)]
    circles = [e for e in sketch.entities.values() if isinstance(e, Circle)]

    if lines:
        vertices, perimeter = _order_polygon_vertices(lines)
        n = len(vertices)
        signed_area = 0.0
        cx_num = 0.0
        cy_num = 0.0
        for i in range(n):
            x_i, y_i = vertices[i]
            x_next, y_next = vertices[(i + 1) % n]
            cross = x_i * y_next - x_next * y_i
            signed_area += cross
            cx_num += (x_i + x_next) * cross
            cy_num += (y_i + y_next) * cross

        signed_area *= 0.5
        area = abs(signed_area)
        cx = cx_num / (6.0 * signed_area) if signed_area != 0.0 else 0.0
        cy = cy_num / (6.0 * signed_area) if signed_area != 0.0 else 0.0

        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        return area, perimeter, cx, cy, (min(xs), max(xs)), (min(ys), max(ys))

    if circles:
        c = circles[0]
        r = c.diameter * 0.5
        area = math.pi * r * r
        perimeter = 2.0 * math.pi * r
        cx, cy = c.center
        return area, perimeter, cx, cy, (cx - r, cx + r), (cy - r, cy + r)

    raise ValueError("Base sketch has no Line or Circle entities")


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


def expected_geometry(graph: PartGraph) -> ExpectedGeometry:
    """Compute expected geometry from a PartGraph alone (spec 10.2, design 9)."""
    features, solid_nodes = _collect_features(graph)

    extrude_entries = [e for e in solid_nodes if e[1].type == "extrude"]
    if not extrude_entries:
        raise ValueError("PartGraph has no solid extrude feature")

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

    cylinders: list[ExpectedCylinder] = []
    base_circles = [e for e in base_sketch_raw.entities.values() if isinstance(e, Circle)]
    if base_circles:
        cylinders.append(
            ExpectedCylinder(
                point=base_plane.to_model(base_cx, base_cy, 0.0),
                direction=base_plane.normal,
                radius=base_circles[0].diameter * 0.5,
            )
        )

    cut_entries = [e for e in solid_nodes if e[1].type == "cut_extrude"]
    for _, cut_node in cut_entries:
        cut_sketch_raw = graph.nodes.get(cut_node.profile)
        if not isinstance(cut_sketch_raw, SketchNode):
            continue

        cut_plane = plane_axes(cut_sketch_raw.plane)
        is_through = cut_node.end_condition.type in ("through_all", "through_all_both")
        cut_depth = base_depth if is_through else float(cut_node.end_condition.depth or 0.0)
        depth_center = cut_depth * 0.5

        for entity in cut_sketch_raw.entities.values():
            if isinstance(entity, Circle):
                r = entity.diameter * 0.5
                hole_vol = math.pi * r * r * cut_depth
                hole_com = cut_plane.to_model(entity.center[0], entity.center[1], depth_center)

                total_volume -= hole_vol
                total_moment[0] -= hole_vol * hole_com[0]
                total_moment[1] -= hole_vol * hole_com[1]
                total_moment[2] -= hole_vol * hole_com[2]

                if is_through:
                    total_area += 2.0 * math.pi * r * cut_depth - 2.0 * math.pi * r * r
                else:
                    total_area += 2.0 * math.pi * r * cut_depth

                cylinders.append(
                    ExpectedCylinder(
                        point=cut_plane.to_model(entity.center[0], entity.center[1], 0.0),
                        direction=cut_plane.normal,
                        radius=r,
                    )
                )

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


def _check_rebuild(m_dict: Mapping[str, JsonValue]) -> CheckResult:
    rebuild_raw = m_dict.get("rebuild")
    rebuild_ok = False
    rebuild_errors: list[str] = []
    if isinstance(rebuild_raw, Mapping):
        rebuild_dict = cast(Mapping[str, JsonValue], rebuild_raw)
        ok_val = rebuild_dict.get("ok")
        if isinstance(ok_val, bool):
            rebuild_ok = ok_val
        errs = rebuild_dict.get("errors")
        if isinstance(errs, list):
            rebuild_errors = [str(e) for e in errs]

    passed = rebuild_ok and len(rebuild_errors) == 0
    measured_json: JsonValue = {
        "ok": rebuild_ok,
        "errors": [cast(JsonValue, e) for e in rebuild_errors],
    }
    expected_json: JsonValue = {
        "ok": True,
        "errors": [],
    }
    return CheckResult(
        requirement="rebuild",
        measured=measured_json,
        expected=expected_json,
        tolerance=None,
        passed=passed,
        method="part.measure.rebuild",
    )


def _check_bodies(m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry) -> CheckResult:
    count_raw = m_dict.get("solid_body_count", 0)
    solid_body_count = int(count_raw) if isinstance(count_raw, int | float) else 0
    passed = solid_body_count == expected.solid_body_count
    return CheckResult(
        requirement="bodies",
        measured=solid_body_count,
        expected=expected.solid_body_count,
        tolerance=None,
        passed=passed,
        method="part.measure.solid_body_count",
    )


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


def _check_features(
    m_dict: Mapping[str, JsonValue],
    expected: ExpectedGeometry,
    feature_ids: Mapping[str, str],
) -> CheckResult:
    features_raw = m_dict.get("features")
    measured_features: list[Mapping[str, JsonValue]] = []
    if isinstance(features_raw, list):
        for f in features_raw:
            if isinstance(f, Mapping):
                measured_features.append(cast(Mapping[str, JsonValue], f))

    measured_by_id: dict[str, Mapping[str, JsonValue]] = {
        str(f.get("feature_id")): f for f in measured_features if "feature_id" in f
    }
    features_passed = len(measured_features) == len(expected.features)

    for exp_feat in expected.features:
        mapped_id = feature_ids.get(exp_feat.node_id)
        if not mapped_id or mapped_id not in measured_by_id:
            features_passed = False
            break
        meas_feat = measured_by_id[mapped_id]
        if meas_feat.get("status") != "ok":
            features_passed = False
            break

        meas_type = str(meas_feat.get("type", ""))
        if not _is_acceptable_feature_type(exp_feat, meas_type):
            features_passed = False
            break

    expected_fids = {
        feature_ids[ef.node_id] for ef in expected.features if ef.node_id in feature_ids
    }
    for f in measured_features:
        fid = str(f.get("feature_id", ""))
        if fid not in expected_fids:
            features_passed = False
            break

    return CheckResult(
        requirement="features",
        measured=len(measured_features),
        expected=len(expected.features),
        tolerance=None,
        passed=features_passed,
        method="part.measure.features",
    )


def _check_bbox(m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry) -> CheckResult:
    bbox_m_raw = m_dict.get("bbox_m")
    min_m: list[float] = [0.0, 0.0, 0.0]
    max_m: list[float] = [0.0, 0.0, 0.0]
    if isinstance(bbox_m_raw, Mapping):
        bbox_dict = cast(Mapping[str, JsonValue], bbox_m_raw)
        min_val = bbox_dict.get("min")
        if isinstance(min_val, list):
            min_m = [float(x) for x in min_val if isinstance(x, int | float)]
        max_val = bbox_dict.get("max")
        if isinstance(max_val, list):
            max_m = [float(x) for x in max_val if isinstance(x, int | float)]

    meas_min_mm = [x * 1000.0 for x in min_m]
    meas_max_mm = [x * 1000.0 for x in max_m]
    exp_min_mm = [expected.bbox_mm.min.x, expected.bbox_mm.min.y, expected.bbox_mm.min.z]
    exp_max_mm = [expected.bbox_mm.max.x, expected.bbox_mm.max.y, expected.bbox_mm.max.z]

    min_ok = all(
        abs(meas_min_mm[i] - exp_min_mm[i]) <= LINEAR_TOLERANCE_MM + 1e-9 for i in range(3)
    )
    max_ok = all(
        abs(meas_max_mm[i] - exp_max_mm[i]) <= LINEAR_TOLERANCE_MM + 1e-9 for i in range(3)
    )
    passed = min_ok and max_ok

    measured_json: JsonValue = {
        "min": [cast(JsonValue, x) for x in meas_min_mm],
        "max": [cast(JsonValue, x) for x in meas_max_mm],
    }
    expected_json: JsonValue = {
        "min": [cast(JsonValue, x) for x in exp_min_mm],
        "max": [cast(JsonValue, x) for x in exp_max_mm],
    }

    return CheckResult(
        requirement="bounding_box",
        measured=measured_json,
        expected=expected_json,
        tolerance=LINEAR_TOLERANCE_MM,
        passed=passed,
        method="part.measure.bbox",
    )


def _check_volume(m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry) -> CheckResult:
    vol_raw = m_dict.get("volume_m3", 0.0)
    vol_m3 = float(vol_raw) if isinstance(vol_raw, int | float) else 0.0
    meas_vol_mm3 = vol_m3 * 1e9
    exp_vol_mm3 = expected.volume_mm3
    vol_diff = abs(meas_vol_mm3 - exp_vol_mm3)
    passed = vol_diff <= (RELATIVE_TOLERANCE_RATIO * exp_vol_mm3 + 1e-9)

    return CheckResult(
        requirement="volume",
        measured=meas_vol_mm3,
        expected=exp_vol_mm3,
        tolerance=RELATIVE_TOLERANCE_RATIO,
        passed=passed,
        method="part.measure.volume",
    )


def _check_surface_area(m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry) -> CheckResult:
    area_raw = m_dict.get("surface_area_m2", 0.0)
    area_m2 = float(area_raw) if isinstance(area_raw, int | float) else 0.0
    meas_area_mm2 = area_m2 * 1e6
    exp_area_mm2 = expected.surface_area_mm2
    area_diff = abs(meas_area_mm2 - exp_area_mm2)
    passed = area_diff <= (RELATIVE_TOLERANCE_RATIO * exp_area_mm2 + 1e-9)

    return CheckResult(
        requirement="surface_area",
        measured=meas_area_mm2,
        expected=exp_area_mm2,
        tolerance=RELATIVE_TOLERANCE_RATIO,
        passed=passed,
        method="part.measure.surface_area",
    )


def _check_center_of_mass(
    m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry
) -> CheckResult:
    com_raw = m_dict.get("center_of_mass_m")
    meas_com_mm: list[float] = [0.0, 0.0, 0.0]
    if isinstance(com_raw, list):
        meas_com_mm = [float(x) * 1000.0 for x in com_raw if isinstance(x, int | float)]
    exp_com_mm = [
        expected.center_of_mass_mm.x,
        expected.center_of_mass_mm.y,
        expected.center_of_mass_mm.z,
    ]
    passed = all(
        abs(meas_com_mm[i] - exp_com_mm[i]) <= LINEAR_TOLERANCE_MM + 1e-9 for i in range(3)
    )

    return CheckResult(
        requirement="center_of_mass",
        measured=[cast(JsonValue, x) for x in meas_com_mm],
        expected=[cast(JsonValue, x) for x in exp_com_mm],
        tolerance=LINEAR_TOLERANCE_MM,
        passed=passed,
        method="part.measure.center_of_mass",
    )


def _check_cylinders(m_dict: Mapping[str, JsonValue], expected: ExpectedGeometry) -> CheckResult:
    cyl_raw = m_dict.get("cylinders_m")
    meas_cyls: list[tuple[tuple[float, float, float], tuple[float, float, float], float]] = []
    if isinstance(cyl_raw, list):
        for c in cyl_raw:
            if isinstance(c, Mapping):
                c_map = cast(Mapping[str, JsonValue], c)
                pt_val = c_map.get("point")
                dir_val = c_map.get("direction")
                rad_val = c_map.get("radius")
                if (
                    isinstance(pt_val, list)
                    and isinstance(dir_val, list)
                    and isinstance(rad_val, int | float)
                ):
                    pt_coords = tuple(
                        float(x) * 1000.0 for x in pt_val if isinstance(x, int | float)
                    )
                    dir_coords = tuple(float(x) for x in dir_val if isinstance(x, int | float))
                    if len(pt_coords) == DIM_3D and len(dir_coords) == DIM_3D:
                        meas_cyls.append((pt_coords, dir_coords, float(rad_val) * 1000.0))

    passed = _match_cylinders(expected.cylinders, meas_cyls)
    return CheckResult(
        requirement="cylinders",
        measured=len(meas_cyls),
        expected=len(expected.cylinders),
        tolerance=LINEAR_TOLERANCE_MM,
        passed=passed,
        method="part.measure.cylinders",
    )


def compare(
    expected: ExpectedGeometry,
    measured: JsonValue,
    feature_ids: Mapping[str, str],
) -> tuple[CheckResult, ...]:
    """Compare expected geometry against raw SI measurements from SOLIDWORKS (spec 10.2).

    Converts raw SI values (m, m2, m3) to mm, mm2, mm3 before checking.
    Never short-circuits: runs every comparison and returns all results.
    """
    m_dict: Mapping[str, JsonValue] = (
        cast(Mapping[str, JsonValue], measured) if isinstance(measured, Mapping) else {}
    )

    return (
        _check_rebuild(m_dict),
        _check_bodies(m_dict, expected),
        _check_features(m_dict, expected, feature_ids),
        _check_bbox(m_dict, expected),
        _check_volume(m_dict, expected),
        _check_surface_area(m_dict, expected),
        _check_center_of_mass(m_dict, expected),
        _check_cylinders(m_dict, expected),
    )
