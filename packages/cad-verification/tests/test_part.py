"""Tests for part verification math and comparisons (spec 10.2, design 9)."""

import math
from typing import Any

import pytest
from cad_ir.part_feature_graph.model import (
    Circle,
    EndCondition,
    Line,
    PartGraph,
    SketchNode,
    SolidNode,
)
from cad_verification.part import (
    compare,
    expected_geometry,
)

EXPECTED_FEATURE_COUNT = 4
EXPECTED_CYLINDER_COUNT = 4
EXPECTED_CHECKS_COUNT = 8
THREE_FAILURES_COUNT = 3


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
