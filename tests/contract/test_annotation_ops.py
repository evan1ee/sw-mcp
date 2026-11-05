"""Contract tests for drawing annotation operations and duplicate cleanup pipeline.

Spec 11.4, 11.10, 11.10.1, 6.5.2.
"""

import pytest
from cad_application.drawing.annotation_ops import (
    plan_annotation_insertion_ops,
    plan_dimension_cleanup_ops,
)
from cad_drawing.checks.geometry2d import Vec
from cad_drawing.checks.snapshot import (
    Annotation,
    PolylineCurve,
    Rect,
    Sheet,
    Snapshot,
    TextBox,
)
from cad_drawing.view_planning.planner import plan_ortho_views
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.drawing_intent import CriticalDimension, DrawingIntent
from cad_ir.drawing_layout.model import DrawingLayout

MODEL_ITEMS_INSERT_SCHEMA_URI = "https://sw-mcp.invalid/schemas/ipc/ops/model_items.insert.json"
CENTER_MARK_ADD_SCHEMA_URI = "https://sw-mcp.invalid/schemas/ipc/ops/center_mark.add.json"
DIMENSIONS_AUTO_ARRANGE_SCHEMA_URI = (
    "https://sw-mcp.invalid/schemas/ipc/ops/dimensions.auto_arrange.json"
)
DIMENSION_HIDE_SCHEMA_URI = "https://sw-mcp.invalid/schemas/ipc/ops/dimension.hide.json"

_EXPECTED_ORTHO_VIEWS_COUNT = 3
_EXPECTED_ARRANGE_SPACING_MM = 10.0
_MIN_SCHEME_ENTRIES_COUNT = 2


@pytest.fixture
def sample_layout() -> DrawingLayout:
    return plan_ortho_views(
        part_extents=(100.0, 50.0, 30.0),
        sheet_size="A3",
        sheet_width_mm=420.0,
        sheet_height_mm=297.0,
        title_block_box=(230.0, 10.0, 410.0, 75.0),
    )


@pytest.fixture
def sample_intent() -> DrawingIntent:
    return DrawingIntent(
        id="intent_bracket_01",
        schema_version="0.1",
        units="mm",
        documents="models/bracket.sldprt",
        critical_dimensions={
            "crit_01": CriticalDimension(param="D1@Sketch1", requirement="Press fit tolerance"),
        },
    )


def _make_sample_snapshot() -> Snapshot:
    v0: Vec = (0.0, 0.0)
    v1: Vec = (10.0, 0.0)
    curve = PolylineCurve(points=(v0, v1))
    tb = TextBox(
        corners=((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)),
        height_mm=3.5,
        method="display_data",
        text="50.00 mm",
    )

    ann_front = Annotation(
        key="ann_d1_front",
        kind="dimension",
        native_id="D1@Sketch1@FrontView",
        tag=None,
        view="Drawing View1",  # Front view
        attachments=(),
        dimension_lines=(curve,),
        extension_lines=(),
        arrowheads=(),
        leaders=(),
        text_boxes=(tb,),
        parameters=("D1@Sketch1",),
    )

    ann_top_dup = Annotation(
        key="ann_d1_top",
        kind="dimension",
        native_id="D1@Sketch1@TopView",
        tag=None,
        view="Drawing View2",  # Top view (redundant duplicate of D1@Sketch1)
        attachments=(),
        dimension_lines=(curve,),
        extension_lines=(),
        arrowheads=(),
        leaders=(),
        text_boxes=(tb,),
        parameters=("D1@Sketch1",),
    )

    ann_unique = Annotation(
        key="ann_d2_top",
        kind="dimension",
        native_id="D2@Sketch1@TopView",
        tag=None,
        view="Drawing View2",
        attachments=(),
        dimension_lines=(curve,),
        extension_lines=(),
        arrowheads=(),
        leaders=(),
        text_boxes=(tb,),
        parameters=("D2@Sketch1",),
    )

    sheet = Sheet(
        key="s1",
        index=1,
        native_id="Sheet1",
        size_mm=(420.0, 297.0),
        border=Rect(min=(10.0, 10.0), max=(410.0, 287.0)),
        title_block=(Rect(min=(230.0, 10.0), max=(410.0, 75.0)),),
        annotations=(ann_front, ann_top_dup, ann_unique),
        views=(),
    )

    return Snapshot(
        schema_version="0.1",
        document="bracket.slddrw",
        revision=None,
        solidworks_version="2025",
        service_pack="0.1",
        captured_at="2026-11-05T00:00:00Z",
        sheets=(sheet,),
        rebuild=None,
    )


def test_plan_annotation_insertion_ops(
    sample_layout: DrawingLayout, sample_intent: DrawingIntent
) -> None:
    view_names = {
        "v_front": "Drawing View1",
        "v_top": "Drawing View2",
        "v_right": "Drawing View3",
        "v_iso": "Drawing View4",
    }
    ops = plan_annotation_insertion_ops(
        layout=sample_layout,
        intent=sample_intent,
        job_prefix="job_ann",
        view_names=view_names,
    )

    assert len(ops) > 0
    # First op must be model_items.insert
    first_op = ops[0]
    assert first_op.op == "model_items.insert"
    assert first_op.operation_id == "job_ann:model_items:0"
    assert first_op.params is not None
    assert isinstance(first_op.params, dict)
    assert first_op.params.get("source") == "entire_model"
    assert first_op.params.get("marked_for_drawing") is True
    assert first_op.params.get("duplicate_dims") is True
    assert first_op.params.get("hole_callouts") is True

    # Validate against JSON schema
    issues = validate_against_schema(first_op.params, MODEL_ITEMS_INSERT_SCHEMA_URI)
    assert len(issues) == 0

    # Next ops should be center_mark.add for 3 ortho views (front, top, right) but not iso
    center_ops = [op for op in ops if op.op == "center_mark.add"]
    assert len(center_ops) == _EXPECTED_ORTHO_VIEWS_COUNT
    for cop in center_ops:
        assert cop.params is not None
        assert isinstance(cop.params, dict)
        assert cop.params.get("hole_centers") is True
        assert cop.params.get("slot_centers") is True
        assert cop.params.get("use_doc_defaults") is True
        assert cop.params.get("view") in [
            "Drawing View1",
            "Drawing View2",
            "Drawing View3",
        ]
        issues = validate_against_schema(cop.params, CENTER_MARK_ADD_SCHEMA_URI)
        assert len(issues) == 0

    # Next ops should be dimensions.auto_arrange for the views
    arrange_ops = [op for op in ops if op.op == "dimensions.auto_arrange"]
    assert len(arrange_ops) == _EXPECTED_ORTHO_VIEWS_COUNT
    for aop in arrange_ops:
        assert aop.params is not None
        assert isinstance(aop.params, dict)
        assert aop.params.get("spacing_mm") == _EXPECTED_ARRANGE_SPACING_MM
        assert aop.params.get("view") in [
            "Drawing View1",
            "Drawing View2",
            "Drawing View3",
        ]
        issues = validate_against_schema(aop.params, DIMENSIONS_AUTO_ARRANGE_SCHEMA_URI)
        assert len(issues) == 0


def test_plan_dimension_cleanup_ops(sample_intent: DrawingIntent) -> None:
    snapshot = _make_sample_snapshot()
    ops, resolved_scheme = plan_dimension_cleanup_ops(
        snapshot=snapshot,
        intent=sample_intent,
        job_prefix="job_clean",
    )

    # There is 1 duplicate: D1 in TopView should be hidden, D1 in FrontView kept
    assert len(ops) == 1
    hide_op = ops[0]
    assert hide_op.op == "dimension.hide"
    assert hide_op.operation_id == "job_clean:hide:0"
    assert hide_op.params is not None
    assert isinstance(hide_op.params, dict)
    assert hide_op.params["annotation"] == "D1@Sketch1@TopView"
    assert hide_op.params.get("reason") == "duplicate"

    # Schema validation
    issues = validate_against_schema(hide_op.params, DIMENSION_HIDE_SCHEMA_URI)
    assert len(issues) == 0

    # Resolved scheme should reflect entries
    assert resolved_scheme is not None
    assert len(resolved_scheme.entries) >= _MIN_SCHEME_ENTRIES_COUNT
    # Verify critical dimension matching from intent
    crit_entries = [
        e for e in resolved_scheme.entries.values() if e.tolerance == {"critical": "crit_01"}
    ]
    assert len(crit_entries) == 1
