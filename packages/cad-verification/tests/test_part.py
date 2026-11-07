"""Tests for part verification math and comparisons (spec 10.2, design 9)."""

import math
from typing import Any

import pytest
from cad_ir.part_feature_graph.model import (
    Arc,
    CenterRectangle,
    Circle,
    CircularPattern,
    CornerRectangle,
    EndCondition,
    Line,
    LinearPattern,
    LinearPatternDirection,
    PartGraph,
    SketchNode,
    SolidNode,
    StraightSlot,
)
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_verification.part import (
    CheckResult,
    ExpectedGeometry,
    compare,
    expected_geometry,
)

EXPECTED_FEATURE_COUNT = 4
EXPECTED_CYLINDER_COUNT = 4
EXPECTED_CHECKS_COUNT = 8
THREE_FAILURES_COUNT = 3
EXPECTED_PATTERN_CYLINDERS = 4
EXPECTED_PATTERN_FEATURES = 5


def make_plate_graph() -> PartGraph:
    """Standard plate fixture from spec 3."""
    return PartGraph(
        id="plate_4h",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "l1": Line(start=(-50.0, -30.0), end=(50.0, -30.0)),
                    "l2": Line(start=(50.0, -30.0), end=(50.0, 30.0)),
                    "l3": Line(start=(50.0, 30.0), end=(-50.0, 30.0)),
                    "l4": Line(start=(-50.0, 30.0), end=(-50.0, -30.0)),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_holes": SketchNode(
                plane="plane:front",
                entities={
                    "c1": Circle(center=(-40.0, -20.0), diameter=8.0),
                    "c2": Circle(center=(40.0, -20.0), diameter=8.0),
                    "c3": Circle(center=(40.0, 20.0), diameter=8.0),
                    "c4": Circle(center=(-40.0, 20.0), diameter=8.0),
                },
            ),
            "cut_holes": SolidNode(
                type="cut_extrude",
                profile="sketch_holes",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_holes", "extrude_base"),
            ),
        },
    )


def make_clean_measurement() -> dict[str, Any]:
    """Clean raw SI measurement from SOLIDWORKS for the plate."""
    return {
        "solid_body_count": 1,
        "bbox_m": {
            "min": [-0.05, -0.03, 0.0],
            "max": [0.05, 0.03, 0.01],
        },
        "volume_m3": 5.798938070170252e-05,
        "surface_area_m2": 0.015803185789489239,
        "center_of_mass_m": [0.0, 0.0, 0.005],
        "cylinders_m": [
            {"point": [-0.04, -0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [0.04, -0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [0.04, 0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [-0.04, 0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        ],
        "rebuild": {
            "ok": True,
            "errors": [],
        },
        "features": [
            {"feature_id": "f73", "native_id": 73, "type": "ProfileFeature", "status": "ok"},
            {"feature_id": "f79", "native_id": 79, "type": "Extrusion", "status": "ok"},
            {"feature_id": "f80", "native_id": 80, "type": "ProfileFeature", "status": "ok"},
            {"feature_id": "f86", "native_id": 86, "type": "ICE", "status": "ok"},
        ],
        "dirty": False,
        "read_only": False,
    }


def make_feature_ids() -> dict[str, str]:
    return {
        "sketch_base": "f73",
        "extrude_base": "f79",
        "sketch_holes": "f80",
        "cut_holes": "f86",
    }


def test_plate_expected() -> None:
    """Verify expected geometry calculated for the standard plate."""
    graph = make_plate_graph()
    geom = expected_geometry(graph)

    assert geom.solid_body_count == 1
    assert geom.volume_mm3 == pytest.approx(57989.38, abs=0.01)
    assert geom.bbox_mm.size == (100.0, 60.0, 10.0)
    assert geom.bbox_mm.min == (-50.0, -30.0, 0.0)
    assert geom.bbox_mm.max == (50.0, 30.0, 10.0)
    assert len(geom.features) == EXPECTED_FEATURE_COUNT
    assert len(geom.cylinders) == EXPECTED_CYLINDER_COUNT
    for c in geom.cylinders:
        assert c.radius == pytest.approx(4.0)

    # Hand-calculated surface area:
    # 2 * 6000 + 320 * 10 + 4 * (2 * pi * 4 * 10 - 2 * pi * 4^2) = 15200 + 192*pi ~ 15803.1858
    expected_area = 15200.0 + 192.0 * math.pi
    assert geom.surface_area_mm2 == pytest.approx(expected_area, rel=1e-5)

    # Hand-calculated center of mass: (0, 0, 5)
    assert geom.center_of_mass_mm == pytest.approx((0.0, 0.0, 5.0), abs=1e-5)


def test_blind_cut_expected() -> None:
    """A Ø10 blind cut 4 mm deep removes pi*25*4, moves CoM, and adds 2*pi*5*4 to area."""
    graph = PartGraph(
        id="blind_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "l1": Line(start=(-50.0, -30.0), end=(50.0, -30.0)),
                    "l2": Line(start=(50.0, -30.0), end=(50.0, 30.0)),
                    "l3": Line(start=(50.0, 30.0), end=(-50.0, 30.0)),
                    "l4": Line(start=(-50.0, 30.0), end=(-50.0, -30.0)),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_cut": SketchNode(
                plane="plane:front",
                entities={
                    "c1": Circle(center=(0.0, 0.0), diameter=10.0),
                },
            ),
            "cut_blind": SolidNode(
                type="cut_extrude",
                profile="sketch_cut",
                end_condition=EndCondition(type="blind", depth=4.0),
                dependencies=("sketch_cut", "extrude_base"),
            ),
        },
    )

    geom = expected_geometry(graph)
    base_volume = 100.0 * 60.0 * 10.0
    removed_volume = math.pi * 25.0 * 4.0
    assert geom.volume_mm3 == pytest.approx(base_volume - removed_volume, rel=1e-5)

    base_area = 2.0 * (100.0 * 60.0) + 2.0 * (100.0 + 60.0) * 10.0
    added_area = 2.0 * math.pi * 5.0 * 4.0
    assert geom.surface_area_mm2 == pytest.approx(base_area + added_area, rel=1e-5)

    # CoM along z moves from 5.0: cut from z=0 to z=4 has centroid z=2
    expected_z = (base_volume * 5.0 - removed_volume * 2.0) / (base_volume - removed_volume)
    assert geom.center_of_mass_mm.z == pytest.approx(expected_z, rel=1e-5)
    center_mid_z = 5.0
    assert geom.center_of_mass_mm.z > center_mid_z


def test_clean_measurement_all_pass() -> None:
    """A clean measurement matching the plate passes every comparison."""
    geom = expected_geometry(make_plate_graph())
    measured = make_clean_measurement()
    feature_ids = make_feature_ids()

    results = compare(geom, measured, feature_ids)
    assert len(results) == EXPECTED_CHECKS_COUNT
    assert all(r.passed for r in results)


def test_si_conversion_literals() -> None:
    """5.798938e-5 m3 reads as 57,989.38 mm3 and units convert accurately."""
    geom = expected_geometry(make_plate_graph())
    measured = make_clean_measurement()
    feature_ids = make_feature_ids()

    results = compare(geom, measured, feature_ids)
    vol_res = next(r for r in results if r.requirement == "volume")
    assert isinstance(vol_res.measured, float)
    assert vol_res.measured == pytest.approx(57989.38, abs=0.01)

    area_res = next(r for r in results if r.requirement == "surface_area")
    assert isinstance(area_res.measured, float)
    assert area_res.measured == pytest.approx(15803.1858, abs=0.01)

    bbox_res = next(r for r in results if r.requirement == "bounding_box")
    assert isinstance(bbox_res.measured, dict)
    assert bbox_res.measured["min"] == pytest.approx([-50.0, -30.0, 0.0])
    assert bbox_res.measured["max"] == pytest.approx([50.0, 30.0, 10.0])


def test_missing_hole_fails_volume() -> None:
    """A part missing one hole (~503 mm3) fails the volume check."""
    geom = expected_geometry(make_plate_graph())
    measured = make_clean_measurement()
    feature_ids = make_feature_ids()

    # Missing one hole: volume is larger by ~502.65 mm3 (5.0265e-7 m3)
    measured["volume_m3"] += (math.pi * 16.0 * 10.0) * 1e-9

    results = compare(geom, measured, feature_ids)
    vol_res = next(r for r in results if r.requirement == "volume")
    assert not vol_res.passed


def test_moved_holes_fail() -> None:
    """F1: symmetric holes moved to (+-20, +-10) have identical volume & box but fail cylinders."""
    geom = expected_geometry(make_plate_graph())
    measured = make_clean_measurement()
    feature_ids = make_feature_ids()

    # Move hole cylinder positions from (+-40, +-20) to (+-20, +-10)
    measured["cylinders_m"] = [
        {"point": [-0.02, -0.01, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        {"point": [0.02, -0.01, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        {"point": [0.02, 0.01, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        {"point": [-0.02, 0.01, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
    ]

    results = compare(geom, measured, feature_ids)
    cyl_res = next(r for r in results if r.requirement == "cylinders")
    assert not cyl_res.passed

    # Volume and bbox still pass
    assert next(r for r in results if r.requirement == "volume").passed
    assert next(r for r in results if r.requirement == "bounding_box").passed


def test_same_area_profile_fails() -> None:
    """F1: a different profile with equal area and box fails surface area."""
    geom = expected_geometry(make_plate_graph())
    measured = make_clean_measurement()
    feature_ids = make_feature_ids()

    # A notched profile with same area & box has larger perimeter -> different surface area
    # Increase surface area by 1% (> 0.01% tolerance)
    measured["surface_area_m2"] *= 1.01

    results = compare(geom, measured, feature_ids)
    area_res = next(r for r in results if r.requirement == "surface_area")
    assert not area_res.passed


def test_within_tolerance_passes() -> None:
    """All Global Constraints tolerances pass when within limits."""
    geom = expected_geometry(make_plate_graph())
    feature_ids = make_feature_ids()

    # 1. Bbox within +-0.01 mm (0.009 mm)
    m = make_clean_measurement()
    m["bbox_m"]["max"][0] += 0.009 * 1e-3
    bbox_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "bounding_box")
    assert bbox_res.passed

    # 2. CoM within +-0.01 mm (0.009 mm)
    m = make_clean_measurement()
    m["center_of_mass_m"][2] += 0.009 * 1e-3
    com_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "center_of_mass")
    assert com_res.passed

    # 3. Cylinders radius within +-0.01 mm (0.009 mm)
    m = make_clean_measurement()
    for c in m["cylinders_m"]:
        c["radius"] += 0.009 * 1e-3
    assert next(r for r in compare(geom, m, feature_ids) if r.requirement == "cylinders").passed

    # 4. Cylinders axis position within +-0.01 mm (0.009 mm)
    m = make_clean_measurement()
    for c in m["cylinders_m"]:
        c["point"][0] += 0.009 * 1e-3
    assert next(r for r in compare(geom, m, feature_ids) if r.requirement == "cylinders").passed

    # 5. Volume within +-0.01% (+0.009%)
    m = make_clean_measurement()
    m["volume_m3"] *= 1.0 + 0.00009
    assert next(r for r in compare(geom, m, feature_ids) if r.requirement == "volume").passed

    # 6. Surface area within +-0.01% (+0.009%)
    m = make_clean_measurement()
    m["surface_area_m2"] *= 1.0 + 0.00009
    assert next(r for r in compare(geom, m, feature_ids) if r.requirement == "surface_area").passed


def test_just_outside_fails() -> None:
    """All Global Constraints tolerances fail when just outside limits."""
    geom = expected_geometry(make_plate_graph())
    feature_ids = make_feature_ids()

    # 1. Bbox outside +-0.01 mm (0.011 mm)
    m = make_clean_measurement()
    m["bbox_m"]["max"][0] += 0.011 * 1e-3
    bbox_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "bounding_box")
    assert not bbox_res.passed

    # 2. CoM outside +-0.01 mm (0.011 mm)
    m = make_clean_measurement()
    m["center_of_mass_m"][2] += 0.011 * 1e-3
    com_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "center_of_mass")
    assert not com_res.passed

    # 3. Cylinders radius outside +-0.01 mm (0.011 mm)
    m = make_clean_measurement()
    m["cylinders_m"][0]["radius"] += 0.011 * 1e-3
    cyl_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "cylinders")
    assert not cyl_res.passed

    # 4. Cylinders axis position outside +-0.01 mm (0.011 mm)
    m = make_clean_measurement()
    m["cylinders_m"][0]["point"][0] += 0.011 * 1e-3
    cyl_pos_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "cylinders")
    assert not cyl_pos_res.passed

    # 5. Volume outside +-0.01% (+0.011%)
    m = make_clean_measurement()
    m["volume_m3"] *= 1.0 + 0.00011
    assert not next(r for r in compare(geom, m, feature_ids) if r.requirement == "volume").passed

    # 6. Surface area outside +-0.01% (+0.011%)
    m = make_clean_measurement()
    m["surface_area_m2"] *= 1.0 + 0.00011
    area_res = next(r for r in compare(geom, m, feature_ids) if r.requirement == "surface_area")
    assert not area_res.passed


def test_rebuild_error_fails() -> None:
    """Rebuild error or rebuild.ok=False fails the rebuild check."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    m["rebuild"]["ok"] = False
    m["rebuild"]["errors"] = ["Failed to rebuild Boss-Extrude1"]
    results = compare(geom, m, make_feature_ids())
    rebuild_res = next(r for r in results if r.requirement == "rebuild")
    assert not rebuild_res.passed


def test_extra_body_fails() -> None:
    """Extra solid body fails the bodies check."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    extra_bodies = 2
    m["solid_body_count"] = extra_bodies
    results = compare(geom, m, make_feature_ids())
    body_res = next(r for r in results if r.requirement == "bodies")
    assert not body_res.passed


def test_extra_feature_fails() -> None:
    """Extra feature in measured features fails the features check."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    m["features"].append(
        {"feature_id": "f99", "native_id": 99, "type": "Extrusion", "status": "ok"}
    )
    results = compare(geom, m, make_feature_ids())
    feat_res = next(r for r in results if r.requirement == "features")
    assert not feat_res.passed


def test_template_default_tree_is_not_an_extra_feature() -> None:
    """A new part always holds folders, three planes and the origin (spike section 3)."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    baseline = [
        {"feature_id": "f1", "native_id": 1, "type": "FavoriteFolder", "status": "ok"},
        {"feature_id": "f2", "native_id": 2, "type": "DetailCabinet", "status": "ok"},
        {"feature_id": "f3", "native_id": 3, "type": "RefPlane", "status": "ok"},
        {"feature_id": "f4", "native_id": 4, "type": "OriginProfileFeature", "status": "ok"},
        {"feature_id": "f5", "native_id": 5, "type": "ConfigTableFolder", "status": "ok"},
    ]
    m["features"] = baseline + list(m["features"])
    results = compare(geom, m, make_feature_ids())
    assert next(r for r in results if r.requirement == "features").passed


def test_sick_feature_fails() -> None:
    """A feature with status != 'ok' fails the features check."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    m["features"][1]["status"] = "error"
    results = compare(geom, m, make_feature_ids())
    feat_res = next(r for r in results if r.requirement == "features")
    assert not feat_res.passed


def test_missing_feature_fails() -> None:
    """A missing feature fails the features check."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    m["features"].pop()
    results = compare(geom, m, make_feature_ids())
    feat_res = next(r for r in results if r.requirement == "features")
    assert not feat_res.passed


def test_wrong_type_with_matching_id_fails() -> None:
    """A feature with matching feature_id but unexpected type fails."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    # f73 should be sketch/ProfileFeature, change to ICE
    m["features"][0]["type"] = "ICE"
    results = compare(geom, m, make_feature_ids())
    feat_res = next(r for r in results if r.requirement == "features")
    assert not feat_res.passed


def test_every_comparison_runs() -> None:
    """Verification runs every comparison and reports all failures at once."""
    geom = expected_geometry(make_plate_graph())
    m = make_clean_measurement()
    # 1. Volume error
    m["volume_m3"] *= 1.2
    # 2. Extra body
    m["solid_body_count"] = 3
    # 3. Rebuild error
    m["rebuild"]["ok"] = False
    m["rebuild"]["errors"] = ["Generic error"]

    results = compare(geom, m, make_feature_ids())
    assert len(results) == EXPECTED_CHECKS_COUNT
    failed = [r for r in results if not r.passed]
    assert len(failed) == THREE_FAILURES_COUNT
    failed_reqs = {r.requirement for r in failed}
    assert failed_reqs == {"volume", "bodies", "rebuild"}


# --- absent or malformed data is not_evaluated, never passed or failed (ADR-063, 8.9.6) ---


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> dict[str, Line]:
    return {
        "a": Line(start=(x0, y0), end=(x1, y0)),
        "b": Line(start=(x1, y0), end=(x1, y1)),
        "c": Line(start=(x1, y1), end=(x0, y1)),
        "d": Line(start=(x0, y1), end=(x0, y0)),
    }


def _plate_with_cut(cut_entities: dict[str, Any], end_condition: EndCondition) -> PartGraph:
    return PartGraph(
        id="plate_cut",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front", entities=_rectangle(-50.0, -30.0, 50.0, 30.0)
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_cut": SketchNode(plane="plane:front", entities=cut_entities),
            "cut": SolidNode(
                type="cut_extrude",
                profile="sketch_cut",
                end_condition=end_condition,
                dependencies=("sketch_cut", "extrude_base"),
            ),
        },
    )


def _plain_plate_geometry() -> ExpectedGeometry:
    """A plate with no holes, so no cylinders are expected."""
    return expected_geometry(
        PartGraph(
            id="plain",
            schema_version="0.1",
            units="mm",
            origin="built",
            nodes={
                "sketch_base": SketchNode(
                    plane="plane:front", entities=_rectangle(-50.0, -30.0, 50.0, 30.0)
                ),
                "extrude_base": SolidNode(
                    type="extrude",
                    profile="sketch_base",
                    end_condition=EndCondition(type="blind", depth=10.0),
                    dependencies=("sketch_base",),
                ),
            },
        )
    )


def _check(results: tuple[CheckResult, ...], requirement: str) -> CheckResult:
    return next(r for r in results if r.requirement == requirement)


def test_clean_measurement_is_status_passed() -> None:
    results = compare(
        expected_geometry(make_plate_graph()), make_clean_measurement(), make_feature_ids()
    )
    assert {r.status for r in results} == {"passed"}
    assert all(r.reason is None for r in results)


def test_real_mismatch_is_status_failed() -> None:
    m = make_clean_measurement()
    m["volume_m3"] *= 1.2
    result = _check(compare(expected_geometry(make_plate_graph()), m, make_feature_ids()), "volume")
    assert result.status == "failed"
    assert result.reason is None


def test_empty_measurement_passes_nothing() -> None:
    """No data at all gives not_evaluated everywhere, including the no-cylinder case."""
    results = compare(_plain_plate_geometry(), {}, {})
    assert len(results) == EXPECTED_CHECKS_COUNT
    assert {r.status for r in results} == {"not_evaluated"}
    assert all(r.reason for r in results)
    assert not any(r.passed for r in results)


def test_non_object_measurement_passes_nothing() -> None:
    results = compare(_plain_plate_geometry(), None, {})
    assert {r.status for r in results} == {"not_evaluated"}


@pytest.mark.parametrize(
    ("key", "requirement"),
    [
        ("rebuild", "rebuild"),
        ("solid_body_count", "bodies"),
        ("features", "features"),
        ("bbox_m", "bounding_box"),
        ("volume_m3", "volume"),
        ("surface_area_m2", "surface_area"),
        ("center_of_mass_m", "center_of_mass"),
        ("cylinders_m", "cylinders"),
    ],
)
def test_missing_field_is_not_evaluated_alone(key: str, requirement: str) -> None:
    m = make_clean_measurement()
    del m[key]
    results = compare(expected_geometry(make_plate_graph()), m, make_feature_ids())
    assert _check(results, requirement).status == "not_evaluated"
    assert all(r.status == "passed" for r in results if r.requirement != requirement)


@pytest.mark.parametrize(
    ("key", "bad", "requirement"),
    [
        ("rebuild", {"ok": True}, "rebuild"),
        ("rebuild", {"ok": "yes", "errors": []}, "rebuild"),
        ("solid_body_count", True, "bodies"),
        ("solid_body_count", 1.5, "bodies"),
        ("features", "none", "features"),
        ("features", [{"feature_id": "f73"}], "features"),
        ("bbox_m", {"min": [-0.05], "max": [0.05]}, "bounding_box"),
        ("bbox_m", {"min": [-0.05, -0.03, 0.0]}, "bounding_box"),
        ("volume_m3", True, "volume"),
        ("volume_m3", float("nan"), "volume"),
        ("surface_area_m2", float("inf"), "surface_area"),
        ("center_of_mass_m", [0.0, 0.0], "center_of_mass"),
        ("cylinders_m", "none", "cylinders"),
        ("cylinders_m", [{"point": [0.0, 0.0, 0.0]}], "cylinders"),
    ],
)
def test_malformed_field_is_not_evaluated(key: str, bad: Any, requirement: str) -> None:
    m = make_clean_measurement()
    m[key] = bad
    result = _check(
        compare(expected_geometry(make_plate_graph()), m, make_feature_ids()), requirement
    )
    assert result.status == "not_evaluated"
    assert result.reason == "malformed_data"


def test_one_malformed_cylinder_among_good_ones_is_not_evaluated() -> None:
    m = make_clean_measurement()
    del m["cylinders_m"][0]["radius"]
    result = _check(
        compare(expected_geometry(make_plate_graph()), m, make_feature_ids()), "cylinders"
    )
    assert result.status == "not_evaluated"


def test_present_empty_cylinders_match_a_part_with_none() -> None:
    m = make_clean_measurement()
    m["cylinders_m"] = []
    result = _check(compare(_plain_plate_geometry(), m, {}), "cylinders")
    assert result.status == "passed"


# --- line-loop cuts, which the design allows (design section 5) ---


def test_rectangular_through_cut_expected() -> None:
    graph = _plate_with_cut(
        _rectangle(10.0, 0.0, 30.0, 20.0), EndCondition(type="through_all_both")
    )
    geom = expected_geometry(graph)
    assert geom.volume_mm3 == pytest.approx(56000.0)
    # Top and bottom each lose 400 mm2; the walls add 80 mm x 10 mm.
    assert geom.surface_area_mm2 == pytest.approx(15200.0)
    assert geom.center_of_mass_mm.x == pytest.approx(-80000.0 / 56000.0)
    assert geom.center_of_mass_mm.y == pytest.approx(-40000.0 / 56000.0)
    assert geom.center_of_mass_mm.z == pytest.approx(5.0)
    assert geom.cylinders == ()


def test_rectangular_blind_cut_expected() -> None:
    graph = _plate_with_cut(
        _rectangle(10.0, 0.0, 30.0, 20.0), EndCondition(type="blind", depth=4.0)
    )
    geom = expected_geometry(graph)
    assert geom.volume_mm3 == pytest.approx(58400.0)
    # The floor replaces the removed top, so only the walls add area.
    assert geom.surface_area_mm2 == pytest.approx(15520.0)
    assert geom.center_of_mass_mm.x == pytest.approx(-32000.0 / 58400.0)
    assert geom.center_of_mass_mm.z == pytest.approx((300000.0 - 3200.0) / 58400.0)


def test_uncut_measurement_fails_a_rectangular_cut() -> None:
    """A cut feature that removed nothing no longer passes the geometry checks."""
    graph = _plate_with_cut(
        _rectangle(10.0, 0.0, 30.0, 20.0), EndCondition(type="through_all_both")
    )
    m = make_clean_measurement()
    m["volume_m3"] = 6.0e-05
    assert _check(compare(expected_geometry(graph), m, {}), "volume").status == "failed"


def _with_status(status: Any, reason: str | None = None) -> CheckResult:
    return CheckResult(
        requirement="r",
        measured=None,
        expected=None,
        tolerance=None,
        status=status,
        method="m",
        reason=reason,
    )


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("warning", None),
        ("not_applicable", "The graph has no blind cut"),
        ("not_evaluated", "not_executed"),
        ("not_evaluated", "unsupported"),
        ("not_evaluated", "missing_data"),
        ("not_evaluated", "malformed_data"),
    ],
)
def test_only_passed_counts_as_passed(status: str, reason: str | None) -> None:
    """ADR-064: warning and not_applicable are separate from a pass, as not_evaluated is."""
    assert _with_status(status, reason).passed is False


def test_passed_status_counts_as_passed() -> None:
    assert _with_status("passed").passed is True


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("not_evaluated", None),
        ("not_evaluated", "backend_said_so"),
        ("not_applicable", None),
        ("not_applicable", ""),
        ("passed", "unsupported"),
        ("failed", "unsupported"),
        ("warning", "unsupported"),
    ],
)
def test_reason_follows_the_status(status: str, reason: str | None) -> None:
    """Spec 8.9.6: only ``not_evaluated`` and ``not_applicable`` carry a reason, and need one."""
    with pytest.raises(ValueError, match="reason"):
        _with_status(status, reason)


# ---- sketches on a cap face (ADR-070) ----

BLOCK_VOLUME = 40 * 30 * 10
HOLE_DEPTH = 4.0
HOLE_DIA = 5.0
HOLE_AREA = math.pi * (HOLE_DIA / 2) ** 2


def _block_with_face_hole(
    plane: str,
    center: tuple[float, float],
    blind: bool = True,
    base_plane: str = "plane:front",
) -> PartGraph:
    box = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
    lines = {
        f"l{i + 1}": {
            "type": "line",
            "start": list(box[i]),
            "end": list(box[(i + 1) % 4]),
        }
        for i in range(4)
    }
    cut_end = {"type": "blind", "depth": HOLE_DEPTH} if blind else {"type": "through_all_both"}
    raw: dict[str, Any] = {
        "module": "part",
        "id": "face_hole",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {"type": "sketch", "plane": base_plane, "entities": lines},
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": plane,
                "dependencies": ["extrude_base"],
                "entities": {
                    "c1": {"type": "circle", "center": list(center), "diameter": HOLE_DIA}
                },
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": cut_end,
            },
        },
    }
    graph = parse_part_graph(raw)
    assert isinstance(graph, PartGraph), graph
    return graph


def test_blind_hole_from_the_end_face() -> None:
    geometry = expected_geometry(_block_with_face_hole("extrude_base.end_face", (0, 0)))
    removed = HOLE_AREA * HOLE_DEPTH
    assert geometry.volume_mm3 == pytest.approx(BLOCK_VOLUME - removed)
    assert geometry.surface_area_mm2 == pytest.approx(
        2 * 1200 + 140 * 10 + math.pi * HOLE_DIA * HOLE_DEPTH
    )
    # The removed material sits between z = 6 and z = 10, centred at z = 8.
    assert geometry.center_of_mass_mm.z == pytest.approx(
        (BLOCK_VOLUME * 5 - removed * 8) / geometry.volume_mm3
    )
    (cyl,) = geometry.cylinders
    assert (cyl.point.x, cyl.point.y, cyl.point.z) == pytest.approx((0, 0, 10))
    assert cyl.radius == pytest.approx(2.5)


def test_blind_hole_from_the_start_face_is_mirrored_in_x() -> None:
    geometry = expected_geometry(_block_with_face_hole("extrude_base.start_face", (10, 5)))
    removed = HOLE_AREA * HOLE_DEPTH
    # Sketch x = +10 on the start face is model x = -10. The hole spans z 0 to 4, centred at 2.
    assert geometry.center_of_mass_mm.x == pytest.approx(removed * 10 / geometry.volume_mm3)
    assert geometry.center_of_mass_mm.z == pytest.approx(
        (BLOCK_VOLUME * 5 - removed * 2) / geometry.volume_mm3
    )
    (cyl,) = geometry.cylinders
    assert (cyl.point.x, cyl.point.y, cyl.point.z) == pytest.approx((-10, 5, 0))


def test_through_hole_from_a_face_removes_the_full_depth() -> None:
    geometry = expected_geometry(
        _block_with_face_hole("extrude_base.end_face", (0, 0), blind=False)
    )
    assert geometry.volume_mm3 == pytest.approx(BLOCK_VOLUME - HOLE_AREA * 10)


@pytest.mark.parametrize(
    ("base_plane", "role", "exp_cyl_pt", "exp_cyl_dir"),
    [
        ("plane:front", "end_face", (10.0, 5.0, 10.0), (0.0, 0.0, 1.0)),
        ("plane:front", "start_face", (-10.0, 5.0, 0.0), (0.0, 0.0, 1.0)),
        ("plane:top", "end_face", (10.0, 10.0, -5.0), (0.0, 1.0, 0.0)),
        ("plane:top", "start_face", (10.0, 0.0, 5.0), (0.0, 1.0, 0.0)),
        ("plane:right", "end_face", (10.0, 5.0, -10.0), (1.0, 0.0, 0.0)),
        ("plane:right", "start_face", (0.0, 5.0, 10.0), (1.0, 0.0, 0.0)),
    ],
)
def test_expected_geometry_all_six_datum_and_cap_combinations(
    base_plane: str,
    role: str,
    exp_cyl_pt: tuple[float, float, float],
    exp_cyl_dir: tuple[float, float, float],
) -> None:
    geometry = expected_geometry(
        _block_with_face_hole(
            f"extrude_base.{role}", (10.0, 5.0), blind=True, base_plane=base_plane
        )
    )
    removed = HOLE_AREA * HOLE_DEPTH
    assert geometry.volume_mm3 == pytest.approx(BLOCK_VOLUME - removed)
    assert geometry.surface_area_mm2 == pytest.approx(
        2 * 1200 + 140 * 10 + math.pi * HOLE_DIA * HOLE_DEPTH
    )
    (cyl,) = geometry.cylinders
    assert (cyl.point.x, cyl.point.y, cyl.point.z) == pytest.approx(exp_cyl_pt)
    assert (cyl.direction.x, cyl.direction.y, cyl.direction.z) == pytest.approx(exp_cyl_dir)
    assert cyl.radius == pytest.approx(2.5)


def test_expected_geometry_with_arcs() -> None:
    slot_graph = PartGraph(
        id="slot_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "l1": Line(start=(-10.0, -10.0), end=(10.0, -10.0)),
                    "a1": Arc(
                        center=(10.0, 0.0),
                        start=(10.0, -10.0),
                        end=(10.0, 10.0),
                        direction="ccw",
                    ),
                    "l2": Line(start=(10.0, 10.0), end=(-10.0, 10.0)),
                    "a2": Arc(
                        center=(-10.0, 0.0),
                        start=(-10.0, 10.0),
                        end=(-10.0, -10.0),
                        direction="ccw",
                    ),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
        },
    )
    geom = expected_geometry(slot_graph)
    expected_vol = 10.0 * (400.0 + math.pi * 100.0)
    assert geom.volume_mm3 == pytest.approx(expected_vol, rel=1e-4)
    assert geom.bbox_mm.min == pytest.approx((-20.0, -10.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((20.0, 10.0, 10.0))
    expected_cylinders_count = 2
    assert len(geom.cylinders) == expected_cylinders_count
    radii = sorted([c.radius for c in geom.cylinders])
    assert radii == pytest.approx([10.0, 10.0])


def test_expected_geometry_with_corner_rectangle() -> None:
    graph = PartGraph(
        id="corner_rect_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sk1": SketchNode(
                plane="plane:front",
                entities={
                    "rect": CornerRectangle(corner1=(0.0, 0.0), corner2=(40.0, 30.0)),
                },
            ),
            "ext1": SolidNode(
                type="extrude",
                profile="sk1",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sk1",),
            ),
        },
    )
    geom = expected_geometry(graph)
    assert geom.volume_mm3 == pytest.approx(12000.0)
    assert geom.bbox_mm.min == pytest.approx((0.0, 0.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((40.0, 30.0, 10.0))
    assert geom.center_of_mass_mm == pytest.approx((20.0, 15.0, 5.0))
    assert geom.surface_area_mm2 == pytest.approx(3800.0)
    assert len(geom.cylinders) == 0


def test_expected_geometry_with_center_rectangle() -> None:
    graph = PartGraph(
        id="center_rect_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sk1": SketchNode(
                plane="plane:front",
                entities={
                    "rect": CenterRectangle(center=(0.0, 0.0), width=50.0, height=20.0),
                },
            ),
            "ext1": SolidNode(
                type="extrude",
                profile="sk1",
                end_condition=EndCondition(type="blind", depth=5.0),
                dependencies=("sk1",),
            ),
        },
    )
    geom = expected_geometry(graph)
    assert geom.volume_mm3 == pytest.approx(5000.0)
    assert geom.bbox_mm.min == pytest.approx((-25.0, -10.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((25.0, 10.0, 5.0))
    assert geom.center_of_mass_mm == pytest.approx((0.0, 0.0, 2.5))
    assert geom.surface_area_mm2 == pytest.approx(2700.0)
    assert len(geom.cylinders) == 0


def test_expected_geometry_with_rectangle_cut() -> None:
    graph = PartGraph(
        id="rect_cut_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sk1": SketchNode(
                plane="plane:front",
                entities={
                    "base_rect": CenterRectangle(center=(0.0, 0.0), width=100.0, height=60.0),
                },
            ),
            "ext1": SolidNode(
                type="extrude",
                profile="sk1",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sk1",),
            ),
            "sk2": SketchNode(
                plane="plane:front",
                entities={
                    "cut_rect": CenterRectangle(center=(0.0, 0.0), width=40.0, height=20.0),
                },
            ),
            "cut1": SolidNode(
                type="cut_extrude",
                profile="sk2",
                end_condition=EndCondition(type="through_all"),
                dependencies=("ext1", "sk2"),
            ),
        },
    )
    geom = expected_geometry(graph)
    assert geom.volume_mm3 == pytest.approx(52000.0)
    assert geom.bbox_mm.min == pytest.approx((-50.0, -30.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((50.0, 30.0, 10.0))
    assert geom.center_of_mass_mm == pytest.approx((0.0, 0.0, 5.0))
    assert geom.surface_area_mm2 == pytest.approx(14800.0)


EXPECTED_SLOT_CYLINDERS = 2


def test_expected_geometry_with_straight_slot() -> None:
    graph = PartGraph(
        id="slot_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sk1": SketchNode(
                plane="plane:front",
                entities={
                    "slot": StraightSlot(
                        start_point=(-20.0, 0.0),
                        end_point=(20.0, 0.0),
                        width=20.0,
                    ),
                },
            ),
            "ext1": SolidNode(
                type="extrude",
                profile="sk1",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sk1",),
            ),
        },
    )
    geom = expected_geometry(graph)
    expected_vol = (800.0 + 100.0 * math.pi) * 10.0
    expected_surf = 2400.0 + 400.0 * math.pi
    assert geom.volume_mm3 == pytest.approx(expected_vol)
    assert geom.bbox_mm.min == pytest.approx((-30.0, -10.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((30.0, 10.0, 10.0))
    assert geom.center_of_mass_mm == pytest.approx((0.0, 0.0, 5.0))
    assert geom.surface_area_mm2 == pytest.approx(expected_surf)
    assert len(geom.cylinders) == EXPECTED_SLOT_CYLINDERS


def test_expected_geometry_with_straight_slot_cut() -> None:
    graph = PartGraph(
        id="plate_slot_cut",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sk1": SketchNode(
                plane="plane:front",
                entities={
                    "base": CenterRectangle(center=(0.0, 0.0), width=100.0, height=60.0),
                },
            ),
            "ext1": SolidNode(
                type="extrude",
                profile="sk1",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sk1",),
            ),
            "sk2": SketchNode(
                plane="plane:front",
                entities={
                    "slot_cut": StraightSlot(
                        start_point=(-20.0, 0.0), end_point=(20.0, 0.0), width=10.0
                    ),
                },
            ),
            "cut1": SolidNode(
                type="cut_extrude",
                profile="sk2",
                end_condition=EndCondition(type="through_all"),
                dependencies=("ext1", "sk2"),
            ),
        },
    )
    geom = expected_geometry(graph)
    base_vol = 100.0 * 60.0 * 10.0
    slot_area = 40.0 * 10.0 + math.pi * 25.0
    slot_perim = 80.0 + math.pi * 10.0
    cut_vol = slot_area * 10.0
    assert geom.volume_mm3 == pytest.approx(base_vol - cut_vol)
    assert geom.bbox_mm.min == pytest.approx((-50.0, -30.0, 0.0))
    assert geom.bbox_mm.max == pytest.approx((50.0, 30.0, 10.0))
    assert geom.center_of_mass_mm == pytest.approx((0.0, 0.0, 5.0))
    expected_surf = (2.0 * 6000.0 + 320.0 * 10.0) + slot_perim * 10.0 - 2.0 * slot_area
    assert geom.surface_area_mm2 == pytest.approx(expected_surf)
    assert len(geom.cylinders) == EXPECTED_SLOT_CYLINDERS


def test_linear_pattern_expected_geometry() -> None:
    """Plate with single hole patterned 4x linearly has 4x cut volume and 4 cylinders."""
    graph = PartGraph(
        id="pattern_plate",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "r1": CenterRectangle(center=(0.0, 0.0), width=100.0, height=60.0),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={"c1": Circle(center=(-30.0, 0.0), diameter=10.0)},
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_hole", "extrude_base"),
            ),
            "pattern_holes": LinearPattern(
                seeds=("cut_hole",),
                direction_1=LinearPatternDirection(
                    direction="plane:right",
                    spacing=20.0,
                    count=4,
                ),
                dependencies=("cut_hole", "extrude_base"),
            ),
        },
    )
    geom = expected_geometry(graph)
    assert geom.solid_body_count == 1
    # 4 through holes of dia 10 (r=5, depth=10):
    # Total hole vol = 4 * pi * 25 * 10 = 1000 * pi ~ 3141.59265
    # Base vol = 100 * 60 * 10 = 60000
    expected_vol = 60000.0 - 1000.0 * math.pi
    assert geom.volume_mm3 == pytest.approx(expected_vol, abs=0.01)
    assert len(geom.cylinders) == EXPECTED_PATTERN_CYLINDERS
    cyl_xs = sorted(c.point.x for c in geom.cylinders)
    assert cyl_xs == pytest.approx([-30.0, -10.0, 10.0, 30.0], abs=1e-4)
    for c in geom.cylinders:
        assert c.radius == pytest.approx(5.0)
    assert len(geom.features) == EXPECTED_PATTERN_FEATURES
    assert geom.features[-1].feature_type == "linear_pattern"
    assert geom.features[-1].native_type == "LPattern"


def test_circular_pattern_expected_geometry() -> None:
    """Cylindrical flange with 6 circular patterned holes."""
    graph = PartGraph(
        id="flange_pattern",
        schema_version="0.1",
        units="mm",
        origin="built",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={"c1": Circle(center=(0.0, 0.0), diameter=100.0)},
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={"c2": Circle(center=(35.0, 0.0), diameter=10.0)},
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all_both"),
                dependencies=("sketch_hole", "extrude_base"),
            ),
            "pattern_holes": CircularPattern(
                seeds=("cut_hole",),
                axis="plane:front",
                count=6,
                spacing=360.0,
                equal_spacing=True,
                dependencies=("cut_hole", "extrude_base"),
            ),
        },
    )
    geom = expected_geometry(graph)
    assert geom.solid_body_count == 1
    # Base: dia 100, depth 10 -> vol = 25000 * pi ~ 78539.816
    # 6 holes: dia 10, depth 10 -> each vol = 250 * pi -> total 1500 * pi ~ 4712.389
    # Net vol = 23500 * pi ~ 73827.427
    expected_vol = 23500.0 * math.pi
    assert geom.volume_mm3 == pytest.approx(expected_vol, abs=0.01)
    # 1 outer cylinder (radius 50) + 6 hole cylinders (radius 5) = 7 cylinders
    expected_cyl_count = 7
    cyl_tol = 1e-3
    assert len(geom.cylinders) == expected_cyl_count
    hole_cyls = [c for c in geom.cylinders if abs(c.radius - 5.0) < cyl_tol]
    expected_hole_cyl_count = 6
    assert len(hole_cyls) == expected_hole_cyl_count
    # All hole cylinders should be at radius 35 from origin
    for c in hole_cyls:
        assert math.hypot(c.point.x, c.point.y) == pytest.approx(35.0, abs=cyl_tol)
    assert len(geom.features) == EXPECTED_PATTERN_FEATURES
    assert geom.features[-1].feature_type == "circular_pattern"
    assert geom.features[-1].native_type == "CirPattern"
