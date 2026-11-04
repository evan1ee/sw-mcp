"""Unit and semantic rule tests for Drawing Template IR (spec 11.12)."""

import json
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cad_ir.core.issues import IssueReport
from cad_ir.drawing_template import (
    MINIMUM_FIELDS,
    PAPER_SIZES_MM,
    TEMPLATE_SCHEMA_ID,
    DrawingTemplate,
    Margins,
    Rect,
    parse_drawing_template,
)
from cad_ir.generated import ErrorCode

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "schemas" / "drawing-template" / "valid" / "full.json"


def _valid_doc() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_schema_id_constant() -> None:
    assert TEMPLATE_SCHEMA_ID == "https://sw-mcp.invalid/schemas/drawing-template/v0.json"


def test_minimum_fields_constant() -> None:
    assert MINIMUM_FIELDS == (
        "part_number",
        "revision",
        "material",
        "finish",
        "general_tolerance",
        "scale",
        "projection_symbol",
        "units",
    )


def test_paper_sizes_constant() -> None:
    assert PAPER_SIZES_MM["A4"] == (210.0, 297.0)
    assert PAPER_SIZES_MM["A3"] == (420.0, 297.0)
    assert PAPER_SIZES_MM["A2"] == (594.0, 420.0)
    assert PAPER_SIZES_MM["A1"] == (841.0, 594.0)
    assert PAPER_SIZES_MM["A0"] == (1189.0, 841.0)


def test_valid_template_parses() -> None:
    doc = _valid_doc()
    res = parse_drawing_template(doc)
    assert isinstance(res, DrawingTemplate)
    assert res.paper_size == "A3"
    assert res.orientation == "landscape"
    assert res.sheet_size_mm == (420.0, 297.0)
    assert res.border_rect == Rect(20.0, 10.0, 410.0, 287.0)
    assert res.margins == Margins(20.0, 10.0, 10.0, 10.0)
    # Check collections are sorted tuples of (key, item)
    zone_keys = [k for k, _ in res.zones]
    assert zone_keys == sorted(zone_keys)
    field_keys = [k for k, _ in res.fields]
    assert field_keys == sorted(field_keys)
    assert res.display_name == "ACME Standard A3"
    assert res.revision_table_box is not None


def test_schema_failure_stops_before_rules() -> None:
    doc = _valid_doc()
    doc["paper"]["size"] = "InvalidSize"
    res = parse_drawing_template(doc)
    assert isinstance(res, IssueReport)
    assert res.has_errors
    assert all(issue.code == ErrorCode.IR_SCHEMA_INVALID for issue in res.issues)


def test_text_normalized_to_nfc() -> None:
    doc = _valid_doc()
    # "e\u0301" is NFD for "é"
    doc["texts"]["company"]["text"] = "ACME\u0301"
    res = parse_drawing_template(doc)
    assert isinstance(res, DrawingTemplate)
    assert res.texts[0][1].text == unicodedata.normalize("NFC", "ACME\u0301")
    assert unicodedata.is_normalized("NFC", res.texts[0][1].text)


# Mutations for rule testing
def _mutate_a4_landscape(doc: dict[str, Any]) -> None:
    doc["paper"]["size"] = "A4"
    doc["paper"]["orientation"] = "landscape"


def _mutate_a3_portrait(doc: dict[str, Any]) -> None:
    doc["paper"]["orientation"] = "portrait"


def _mutate_margins_too_big(doc: dict[str, Any]) -> None:
    doc["border"]["margins"]["left"] = 500.0


def _mutate_inverted_zone(doc: dict[str, Any]) -> None:
    doc["title_block"]["zones"]["main"]["min"] = [250.0, 70.0]
    doc["title_block"]["zones"]["main"]["max"] = [240.0, 50.0]


def _mutate_inverted_box(doc: dict[str, Any]) -> None:
    doc["fields"]["part_number"]["box"]["min"] = [250.0, 60.0]
    doc["fields"]["part_number"]["box"]["max"] = [240.0, 50.0]


def _mutate_zone_outside_border(doc: dict[str, Any]) -> None:
    # Border max x is 410 (420 - 10)
    doc["title_block"]["zones"]["main"]["max"] = [415.0, 120.0]


def _mutate_zones_overlap(doc: dict[str, Any]) -> None:
    # Zone main is [230, 10] to [410, 120]
    # Add zone sub overlapping with main
    doc["title_block"]["zones"]["sub"] = {
        "min": [250.0, 20.0],
        "max": [300.0, 80.0],
    }


def _mutate_line_zero_length(doc: dict[str, Any]) -> None:
    doc["title_block"]["lines"]["top_line"]["from"] = [250.0, 50.0]
    doc["title_block"]["lines"]["top_line"]["to"] = [250.0, 50.0]


def _mutate_line_outside_zone(doc: dict[str, Any]) -> None:
    # Line leaves zone main [230, 10] to [410, 120]
    doc["title_block"]["lines"]["top_line"]["from"] = [200.0, 50.0]
    doc["title_block"]["lines"]["top_line"]["to"] = [250.0, 50.0]


def _mutate_text_outside_border(doc: dict[str, Any]) -> None:
    # Border max y is 287 (297 - 10). Put text box above border
    doc["texts"]["company"]["box"]["min"] = [250.0, 285.0]
    doc["texts"]["company"]["box"]["max"] = [300.0, 295.0]


def _mutate_field_outside_zone(doc: dict[str, Any]) -> None:
    # Zone max y is 120. Put field box at [232, 125] to [300, 135]
    doc["fields"]["part_number"]["box"]["min"] = [232.0, 125.0]
    doc["fields"]["part_number"]["box"]["max"] = [300.0, 135.0]


def _mutate_field_straddles_zones(doc: dict[str, Any]) -> None:
    # Two touching zones: z1 [230, 10] to [300, 120], z2 [300, 10] to [410, 120]
    doc["title_block"]["zones"] = {
        "z1": {"min": [230.0, 10.0], "max": [300.0, 120.0]},
        "z2": {"min": [300.0, 10.0], "max": [410.0, 120.0]},
    }
    # Keep line and revision table in one zone each
    doc["title_block"]["lines"]["top_line"]["to"] = [300.0, 120.0]
    doc["revision_table"]["box"] = {
        "min": [305.0, 70.0],
        "max": [408.0, 95.0],
    }
    # Field box crosses x=300 at y in [60, 68] so it does not overlap with any other box
    doc["fields"]["part_number"]["box"]["min"] = [290.0, 60.0]
    doc["fields"]["part_number"]["box"]["max"] = [310.0, 68.0]


def _mutate_revision_table_outside_zone(doc: dict[str, Any]) -> None:
    doc["revision_table"]["box"]["min"] = [232.0, 125.0]
    doc["revision_table"]["box"]["max"] = [408.0, 150.0]


def _mutate_boxes_overlap(doc: dict[str, Any]) -> None:
    # Overlap text box with field box
    doc["texts"]["company"]["box"]["min"] = [232.0, 50.0]
    doc["texts"]["company"]["box"]["max"] = [300.0, 58.0]


def _mutate_text_taller_than_box(doc: dict[str, Any]) -> None:
    # Box height is 8 (50 to 58). Height is 10
    doc["fields"]["part_number"]["height"] = 10.0


def _mutate_minimum_field_missing(doc: dict[str, Any]) -> None:
    del doc["fields"]["finish"]


def _mutate_all_fields_missing(doc: dict[str, Any]) -> None:
    # Replace fields with non-minimum field to pass minProperties: 1
    doc["fields"] = {
        "custom_field": {
            "source": ["part_property:Custom"],
            "box": {"min": [232.0, 50.0], "max": [300.0, 58.0]},
            "height": 3.5,
        }
    }


def _mutate_minimum_not_required(doc: dict[str, Any]) -> None:
    doc["fields"]["finish"]["required"] = False


def _mutate_source_order(doc: dict[str, Any]) -> None:
    # part_property (rank 2) before design_intent (rank 0)
    doc["fields"]["part_number"]["source"] = [
        "part_property:PartNo",
        "design_intent:metadata.part_number",
    ]


def _mutate_sheet_source_not_alone(doc: dict[str, Any]) -> None:
    doc["fields"]["scale"]["source"] = ["sheet:scale", "part_property:Scale"]


@pytest.mark.parametrize(
    ("mutate", "expected_pointers"),
    [
        (_mutate_a4_landscape, ["/paper/orientation"]),
        (_mutate_a3_portrait, ["/paper/orientation"]),
        (_mutate_margins_too_big, ["/border/margins"]),
        (_mutate_inverted_zone, ["/title_block/zones/main"]),
        (_mutate_inverted_box, ["/fields/part_number/box"]),
        (_mutate_zone_outside_border, ["/title_block/zones/main"]),
        (_mutate_zones_overlap, ["/title_block/zones/sub"]),
        (_mutate_line_zero_length, ["/title_block/lines/top_line"]),
        (_mutate_line_outside_zone, ["/title_block/lines/top_line"]),
        (_mutate_text_outside_border, ["/texts/company/box"]),
        (_mutate_field_outside_zone, ["/fields/part_number/box"]),
        (_mutate_field_straddles_zones, ["/fields/part_number/box"]),
        (_mutate_revision_table_outside_zone, ["/revision_table/box"]),
        (_mutate_boxes_overlap, ["/texts/company/box"]),
        (_mutate_text_taller_than_box, ["/fields/part_number/height"]),
        (_mutate_minimum_field_missing, ["/fields"]),
        (
            _mutate_all_fields_missing,
            ["/fields"] * 8,
        ),
        (_mutate_minimum_not_required, ["/fields/finish/required"]),
        (_mutate_source_order, ["/fields/part_number/source"]),
        (_mutate_sheet_source_not_alone, ["/fields/scale/source"]),
    ],
)
def test_rule_violation(
    mutate: Callable[[dict[str, Any]], None], expected_pointers: list[str]
) -> None:
    doc = _valid_doc()
    mutate(doc)
    res = parse_drawing_template(doc)
    assert isinstance(res, IssueReport)
    assert res.has_errors
    assert all(issue.code == ErrorCode.IR_RULE_VIOLATED for issue in res.issues)
    assert [issue.pointer for issue in res.issues] == expected_pointers


def test_touching_zones_pass() -> None:
    doc = _valid_doc()
    doc["title_block"]["zones"] = {
        "z1": {"min": [230.0, 10.0], "max": [300.0, 120.0]},
        "z2": {"min": [300.0, 10.0], "max": [410.0, 120.0]},
    }
    doc["title_block"]["lines"]["top_line"]["to"] = [300.0, 120.0]
    doc["revision_table"]["box"] = {
        "min": [305.0, 70.0],
        "max": [408.0, 95.0],
    }
    res = parse_drawing_template(doc)
    assert isinstance(res, DrawingTemplate)


def test_edges_within_quantum_pass() -> None:
    doc = _valid_doc()
    # 230 and 230.0000004 differ by 4e-7, which is within the 1e-6 mm quantum
    doc["title_block"]["zones"]["main"]["min"] = [230.0000004, 10.0]
    res = parse_drawing_template(doc)
    assert isinstance(res, DrawingTemplate)


def test_explicit_required_true_passes() -> None:
    doc = _valid_doc()
    for field in doc["fields"].values():
        field["required"] = True
    res = parse_drawing_template(doc)
    assert isinstance(res, DrawingTemplate)


def test_several_failures_all_reported() -> None:
    doc = _valid_doc()
    _mutate_a4_landscape(doc)
    _mutate_minimum_not_required(doc)
    res = parse_drawing_template(doc)
    assert isinstance(res, IssueReport)
    pointers = [issue.pointer for issue in res.issues]
    assert "/paper/orientation" in pointers
    assert "/fields/finish/required" in pointers


def test_same_document_same_issue_order() -> None:
    doc = _valid_doc()
    _mutate_a4_landscape(doc)
    _mutate_minimum_not_required(doc)
    res1 = parse_drawing_template(doc)
    res2 = parse_drawing_template(doc)
    assert isinstance(res1, IssueReport)
    assert isinstance(res2, IssueReport)
    assert [i.pointer for i in res1.issues] == [i.pointer for i in res2.issues]
