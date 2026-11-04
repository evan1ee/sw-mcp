"""Tests for check D8 with DrawingTemplate-derived mappings (ADR-055, K7)."""

from cad_drawing.checks import TitleBlockMapping, check_d8, mapping_from_drawing_template
from cad_drawing.checks.snapshot import Rect as SnapshotRect
from cad_drawing.checks.snapshot import RevisionTable, Sheet, Snapshot
from cad_ir.drawing_template.model import (
    DrawingTemplate,
    Margins,
    Rect,
    TemplateField,
)


def _sample_template() -> DrawingTemplate:
    fields = (
        (
            "part_number",
            TemplateField(
                "part_number", ("part_property:PartNo",), True, None, Rect(0, 0, 10, 10), 3.5
            ),
        ),
        (
            "revision",
            TemplateField(
                "revision", ("drawing_property:Revision",), True, None, Rect(10, 0, 20, 10), 3.5
            ),
        ),
        (
            "material",
            TemplateField("material", ("part_material",), True, None, Rect(20, 0, 30, 10), 3.5),
        ),
        (
            "finish",
            TemplateField(
                "finish", ("drawing_intent:finish",), True, None, Rect(30, 0, 40, 10), 3.5
            ),
        ),
        (
            "general_tolerance",
            TemplateField(
                "general_tolerance", ("drawing_intent:tol",), True, None, Rect(40, 0, 50, 10), 3.5
            ),
        ),
        ("scale", TemplateField("scale", ("sheet:scale",), True, None, Rect(50, 0, 60, 10), 3.5)),
        (
            "projection_symbol",
            TemplateField(
                "projection_symbol", ("sheet:projection",), True, None, Rect(60, 0, 70, 10), 3.5
            ),
        ),
        ("units", TemplateField("units", ("sheet:units",), True, None, Rect(70, 0, 80, 10), 3.5)),
        (
            "custom_opt",
            TemplateField(
                "custom_opt", ("part_property:Custom",), False, None, Rect(80, 0, 90, 10), 3.5
            ),
        ),
    )
    return DrawingTemplate(
        id="ACME-A3",
        schema_version="0.1",
        display_name="ACME A3",
        paper_size="A3",
        orientation="landscape",
        margins=Margins(20.0, 10.0, 10.0, 10.0),
        border_line_width=0.5,
        zones=(),
        lines=(),
        texts=(),
        fields=fields,
        revision_table_box=Rect(0, 0, 50, 20),
    )


def test_mapping_from_drawing_template() -> None:
    template = _sample_template()
    mapping = mapping_from_drawing_template(template)
    assert isinstance(mapping, TitleBlockMapping)
    assert mapping.template == "ACME-A3"
    assert mapping.revision_table is True
    # custom_opt is optional, so it should not be in required
    assert "custom_opt" not in mapping.required
    assert "part_number" in mapping.required


def test_d8_evaluates_cleanly_with_template_mapping() -> None:
    template = _sample_template()
    mapping = mapping_from_drawing_template(template)
    mappings = {mapping.template: mapping}

    sheet = Sheet(
        key="s1",
        index=0,
        native_id="Sheet1",
        size_mm=(420.0, 297.0),
        border=SnapshotRect(min=(20.0, 10.0), max=(410.0, 287.0)),
        title_block=(),
        views=(),
        annotations=(),
        sheet_format="ACME-A3",
        title_block_fields=(
            ("part_number", "123-456"),
            ("revision", "B"),
            ("material", "AISI 304"),
            ("finish", "Ra 1.6"),
            ("general_tolerance", "ISO 2768-m"),
            ("scale", "1:1"),
            ("projection_symbol", "first_angle"),
            ("units", "mm"),
        ),
        revision_table=RevisionTable(entries=("A", "B")),
    )
    snapshot = Snapshot(
        schema_version="0.1",
        document="test.slddrw",
        revision=1,
        solidworks_version="2025",
        service_pack="SP0.0",
        captured_at="2026-11-04T12:00:00Z",
        sheets=(sheet,),
    )

    outcome = check_d8(snapshot, mappings)
    assert outcome.status == "pass"
    assert outcome.failures == ()
