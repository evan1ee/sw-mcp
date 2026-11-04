"""Unit tests for pure view planning engine (spec 11.2, 11.4, 11.11)."""

from cad_drawing.view_planning import (
    ISO_SCALES,
    format_scale_string,
    parse_scale_string,
    plan_ortho_views,
    select_iso_scale,
)
from cad_ir.drawing_layout import DrawingLayout

TITLE_BLOCK_A3 = (240.0, 0.0, 420.0, 65.0)  # [min_x, min_y, max_x, max_y] in mm
EPSILON = 1e-6
MIN_ENLARGEMENT_RATIO = 2.0
MAX_REDUCTION_RATIO = 0.2
MIN_ISO_Y = 100.0


def test_iso_scales_defined() -> None:
    assert (1, 1) in ISO_SCALES
    assert (1, 2) in ISO_SCALES
    assert (1, 5) in ISO_SCALES
    assert (2, 1) in ISO_SCALES


def test_scale_string_roundtrip() -> None:
    assert parse_scale_string("1:1") == (1, 1)
    assert parse_scale_string("1:2") == (1, 2)
    assert parse_scale_string("5:1") == (5, 1)
    assert format_scale_string(1, 2) == "1:2"
    assert format_scale_string(2, 1) == "2:1"


def test_select_iso_scale_small_part() -> None:
    # Small 15mm part on A3 sheet should pick enlargement scale
    scale_num, scale_den = select_iso_scale(
        part_width_mm=15.0,
        part_height_mm=10.0,
        part_depth_mm=5.0,
        usable_width_mm=360.0,
        usable_height_mm=240.0,
        spacing_mm=25.0,
    )
    scale_val = scale_num / scale_den
    assert scale_val >= MIN_ENLARGEMENT_RATIO


def test_select_iso_scale_medium_part() -> None:
    # 100x60x40 mm part on A3 sheet (420x297 mm) comfortably fits at 1:1
    scale_num, scale_den = select_iso_scale(
        part_width_mm=100.0,
        part_height_mm=60.0,
        part_depth_mm=40.0,
        usable_width_mm=350.0,
        usable_height_mm=220.0,
        spacing_mm=25.0,
    )
    assert (scale_num, scale_den) == (1, 1)


def test_select_iso_scale_large_part() -> None:
    # 800x600x400 mm part requires reduction scale
    scale_num, scale_den = select_iso_scale(
        part_width_mm=800.0,
        part_height_mm=600.0,
        part_depth_mm=400.0,
        usable_width_mm=350.0,
        usable_height_mm=220.0,
        spacing_mm=25.0,
    )
    scale_val = scale_num / scale_den
    assert scale_val <= MAX_REDUCTION_RATIO


def test_plan_ortho_views_first_angle_geometry() -> None:
    layout = plan_ortho_views(
        part_extents=(100.0, 60.0, 40.0),
        sheet_size="A3",
        sheet_width_mm=420.0,
        sheet_height_mm=297.0,
        title_block_box=TITLE_BLOCK_A3,
        include_isometric=True,
        intent_ref="drawing_intent:BRK-001-DI@1",
    )
    assert isinstance(layout, DrawingLayout)
    assert len(layout.sheets) == 1
    assert "s1" in layout.sheets

    views = layout.views
    assert "v_front" in views
    assert "v_top" in views
    assert "v_right" in views
    assert "v_iso" in views

    front = views["v_front"]
    top = views["v_top"]
    right = views["v_right"]
    iso = views["v_iso"]

    # ISO 5456-2 First-Angle Projection alignment rules:
    # 1. Front and Top share identical X position (vertical alignment)
    assert abs(top.position[0] - front.position[0]) < EPSILON
    # 2. Top view is projected BELOW Front view in first-angle
    assert top.position[1] < front.position[1]
    # 3. Front and Right share identical Y position (horizontal alignment)
    assert abs(right.position[1] - front.position[1]) < EPSILON
    # 4. Right view is projected to the LEFT of Front view in first-angle
    assert right.position[0] < front.position[0]
    # 5. Isometric view is in top-right or upper quadrant clear of title block
    assert iso.position[1] > MIN_ISO_Y
    assert iso.position[0] > 0.0


def test_plan_ortho_views_title_block_avoidance() -> None:
    layout = plan_ortho_views(
        part_extents=(120.0, 80.0, 50.0),
        sheet_size="A3",
        sheet_width_mm=420.0,
        sheet_height_mm=297.0,
        title_block_box=TITLE_BLOCK_A3,
        include_isometric=True,
    )
    # Check that no view center is inside the title block
    tb_min_x, tb_min_y, tb_max_x, tb_max_y = TITLE_BLOCK_A3
    for view_id, view in layout.views.items():
        x, y = view.position
        in_title_block = (tb_min_x <= x <= tb_max_x) and (tb_min_y <= y <= tb_max_y)
        assert not in_title_block, f"View {view_id} placed inside title block at ({x}, {y})"


def test_plan_ortho_views_determinism() -> None:
    extents = (95.0, 45.0, 30.0)
    layout1 = plan_ortho_views(extents, sheet_size="A3")
    layout2 = plan_ortho_views(extents, sheet_size="A3")
    assert layout1.to_dict() == layout2.to_dict()
