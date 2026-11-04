"""Unit tests for Drawing Layout IR (spec 11.11)."""

import json
from pathlib import Path
from typing import Any

from cad_ir.core.issues import IssueReport
from cad_ir.drawing_layout import (
    LAYOUT_SCHEMA_ID,
    DrawingAnnotation,
    DrawingLayout,
    DrawingSheet,
    DrawingView,
    parse_drawing_layout,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "schemas" / "drawing-layout"
EXPECTED_VIEWS_COUNT = 4


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_id_constant() -> None:
    assert LAYOUT_SCHEMA_ID == "https://sw-mcp.invalid/schemas/drawing-layout/v0.json"


def test_valid_minimal_layout_parses() -> None:
    doc = _load(FIXTURES_DIR / "valid" / "minimal.json")
    res = parse_drawing_layout(doc)
    assert isinstance(res, DrawingLayout)
    assert res.id == "BRK-001-DL"
    assert res.schema_version == "0.1"
    assert res.units == "mm"
    assert res.intent == "drawing_intent:BRK-001-DI@1"
    assert len(res.sheets) == 1
    sheet = res.sheets["s1"]
    assert isinstance(sheet, DrawingSheet)
    assert sheet.size == "A3"
    assert sheet.orientation == "landscape"
    assert sheet.scale == "1:1"

    assert len(res.views) == 1
    view = res.views["v_front"]
    assert isinstance(view, DrawingView)
    assert view.sheet == "s1"
    assert view.type == "base"
    assert view.orientation == "front"
    assert view.position == (150.0, 150.0)
    assert view.scale == "1:1"


def test_valid_three_view_a3_layout_parses() -> None:
    doc = _load(FIXTURES_DIR / "valid" / "three_view_a3.json")
    res = parse_drawing_layout(doc)
    assert isinstance(res, DrawingLayout)
    assert res.part_path == "C:\\Models\\bracket.sldprt"
    assert len(res.views) == EXPECTED_VIEWS_COUNT

    front = res.views["v_front"]
    assert front.display.hidden_lines is False
    assert front.display.tangent_edges == "removed"

    top = res.views["v_top"]
    assert top.type == "projected"
    assert top.parent == "v_front"
    assert top.position == (180.0, 80.0)

    right = res.views["v_right"]
    assert right.type == "projected"
    assert right.parent == "v_front"

    iso = res.views["v_iso"]
    assert iso.type == "isometric"
    assert iso.scale == "1:2"

    assert len(res.annotations) == 1
    ann = res.annotations["a_bore_dia"]
    assert isinstance(ann, DrawingAnnotation)
    assert ann.kind == "dimension"
    assert ann.intent_ref == "scheme:ds_bore_1_diameter_b41219"
    assert ann.view == "v_front"
    assert ann.text_position == (190.0, 185.0)
    assert ann.tag == "sp:a_bore_dia"
    assert ann.placed_by == "manual"
    assert ann.pinned is True

    # Test roundtrip serialization
    d = res.to_dict()
    roundtrip = parse_drawing_layout(d)
    assert isinstance(roundtrip, DrawingLayout)
    assert roundtrip.id == res.id
    assert roundtrip.views["v_front"].position == res.views["v_front"].position


def test_invalid_layout_rejected() -> None:
    doc = _load(FIXTURES_DIR / "invalid" / "wrong_module.json")
    res = parse_drawing_layout(doc)
    assert isinstance(res, IssueReport)
    assert len(res.issues) > 0
