"""Contract tests for Drawing Layout to IPC operations mapping and as-built derivation.

Spec 11.4, 11.11, 6.5.2.
"""

import pytest
from cad_application.drawing.layout_ops import derive_as_built_layout, layout_to_create_ops
from cad_drawing.view_planning.planner import plan_ortho_views
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.drawing_layout.model import DrawingLayout

VIEW_CREATE_SCHEMA_URI = "https://sw-mcp.invalid/schemas/ipc/ops/view.create.json"


_EXPECTED_COORDS = 2


@pytest.fixture
def sample_layout() -> DrawingLayout:
    return plan_ortho_views(
        part_extents=(100.0, 50.0, 30.0),
        sheet_size="A3",
        sheet_width_mm=420.0,
        sheet_height_mm=297.0,
        title_block_box=(230.0, 10.0, 410.0, 75.0),
    )


def test_layout_to_create_ops_produces_valid_ops(sample_layout: DrawingLayout) -> None:
    ops = layout_to_create_ops(
        layout=sample_layout,
        model_path="C:/models/bracket.sldprt",
        job_prefix="job_test",
    )

    assert len(ops) == len(sample_layout.views)
    for idx, op in enumerate(ops):
        assert op.op == "view.create"
        assert op.operation_id == f"job_test:{idx}"
        assert op.params is not None
        assert isinstance(op.params, dict)
        assert op.params["model_path"] == "C:/models/bracket.sldprt"
        assert op.params["sheet"] == "s1"
        assert "scale" in op.params
        assert "position" in op.params
        pos = op.params["position"]
        assert isinstance(pos, list)
        assert len(pos) == _EXPECTED_COORDS

        # Validate against official JSON schema
        issues = validate_against_schema(op.params, VIEW_CREATE_SCHEMA_URI)
        assert len(issues) == 0


def test_derive_as_built_layout(sample_layout: DrawingLayout) -> None:
    # Synthetic snapshot matching drawing-geometry-snapshot schema
    snapshot: dict[str, JsonValue] = {
        "schema_version": "0.1",
        "drawing": {"document": "C:/temp/drawing.slddrw", "revision": None},
        "solidworks": {"version": "2025", "service_pack": "0.1"},
        "captured_at": "2026-11-04T12:00:00Z",
        "sheets": {
            "s_sheet1": {
                "index": 1,
                "native_id": "Sheet1",
                "size_mm": [420.0, 297.0],
                "border": {"min": [10.0, 10.0], "max": [410.0, 287.0]},
                "title_block": [{"min": [230.0, 10.0], "max": [410.0, 75.0]}],
                "views": {
                    "v_front": {
                        "native_id": "Front",
                        "scale": 1.0,
                        "outline": {"min": [80.0, 120.0], "max": [180.0, 170.0]},
                        "edges": [],
                    },
                    "v_top": {
                        "native_id": "Top",
                        "scale": 1.0,
                        "outline": {"min": [80.0, 40.0], "max": [180.0, 70.0]},
                        "edges": [],
                    },
                    "v_right": {
                        "native_id": "Right",
                        "scale": 1.0,
                        "outline": {"min": [20.0, 120.0], "max": [50.0, 170.0]},
                        "edges": [],
                    },
                    "v_iso": {
                        "native_id": "Isometric",
                        "scale": 1.0,
                        "outline": {"min": [240.0, 150.0], "max": [350.0, 230.0]},
                        "edges": [],
                    },
                },
                "annotations": {},
            }
        },
        "rebuild": {
            "completed": True,
            "errors": [],
            "silhouette_attachments": [],
            "reopen": "not_checked",
        },
    }

    as_built = derive_as_built_layout(snapshot, sample_layout)
    assert len(as_built.views) == len(sample_layout.views)
    front_view = next(v for v in as_built.views.values() if v.orientation == "front")
    assert front_view.position == (130.0, 145.0)
