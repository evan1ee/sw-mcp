"""Parser and validation driver for Drawing Template IR (spec 11.12)."""

from typing import cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.core.text import normalize_text
from cad_ir.drawing_template.model import (
    DrawingTemplate,
    Margins,
    Rect,
    StaticText,
    TemplateField,
    TitleBlockLine,
)
from cad_ir.drawing_template.rules import (
    MINIMUM_FIELDS,
    TEMPLATE_SCHEMA_ID,
    semantic_issues,
)


def _rect(obj: dict[str, JsonValue]) -> Rect:
    min_pt = cast(list[float], obj["min"])
    max_pt = cast(list[float], obj["max"])
    return Rect(
        min_x=float(min_pt[0]),
        min_y=float(min_pt[1]),
        max_x=float(max_pt[0]),
        max_y=float(max_pt[1]),
    )


def _margins(obj: dict[str, JsonValue]) -> Margins:
    return Margins(
        left=float(obj["left"]),  # type: ignore[arg-type]
        right=float(obj["right"]),  # type: ignore[arg-type]
        top=float(obj["top"]),  # type: ignore[arg-type]
        bottom=float(obj["bottom"]),  # type: ignore[arg-type]
    )


def _parse_zones(title_block_dict: dict[str, JsonValue]) -> tuple[tuple[str, Rect], ...]:
    raw_zones = cast(dict[str, dict[str, JsonValue]], title_block_dict["zones"])
    return tuple((k, _rect(raw_zones[k])) for k in sorted(raw_zones))


def _parse_lines(
    title_block_dict: dict[str, JsonValue],
) -> tuple[tuple[str, TitleBlockLine], ...]:
    raw_lines = cast(dict[str, dict[str, JsonValue]], title_block_dict.get("lines", {}))
    lines_list: list[tuple[str, TitleBlockLine]] = []
    for k in sorted(raw_lines):
        line_dict = raw_lines[k]
        from_pt = cast(list[float], line_dict["from"])
        to_pt = cast(list[float], line_dict["to"])
        lw = line_dict.get("line_width")
        line_obj = TitleBlockLine(
            key=k,
            start=(float(from_pt[0]), float(from_pt[1])),
            end=(float(to_pt[0]), float(to_pt[1])),
            line_width=float(lw) if lw is not None else None,  # type: ignore[arg-type]
        )
        lines_list.append((k, line_obj))
    return tuple(lines_list)


def _parse_texts(doc: dict[str, JsonValue]) -> tuple[tuple[str, StaticText], ...]:
    raw_texts = cast(dict[str, dict[str, JsonValue]], doc.get("texts", {}))
    texts_list: list[tuple[str, StaticText]] = []
    for k in sorted(raw_texts):
        text_dict = raw_texts[k]
        align_val = text_dict.get("align")
        static_text = StaticText(
            key=k,
            text=normalize_text(str(text_dict["text"])),
            box=_rect(cast(dict[str, JsonValue], text_dict["box"])),
            height=float(text_dict["height"]),  # type: ignore[arg-type]
            align=str(align_val) if align_val is not None else None,
        )
        texts_list.append((k, static_text))
    return tuple(texts_list)


def _parse_fields(doc: dict[str, JsonValue]) -> tuple[tuple[str, TemplateField], ...]:
    raw_fields = cast(dict[str, dict[str, JsonValue]], doc["fields"])
    fields_list: list[tuple[str, TemplateField]] = []
    for k in sorted(raw_fields):
        field_dict = raw_fields[k]
        sources = tuple(str(s) for s in cast(list[JsonValue], field_dict["source"]))
        req_val = field_dict.get("required")
        required = bool(req_val) if req_val is not None else k in MINIMUM_FIELDS

        raw_label = field_dict.get("label")
        label = normalize_text(str(raw_label)) if raw_label is not None else None
        align_val = field_dict.get("align")

        template_field = TemplateField(
            key=k,
            source=sources,
            required=required,
            label=label,
            box=_rect(cast(dict[str, JsonValue], field_dict["box"])),
            height=float(field_dict["height"]),  # type: ignore[arg-type]
            align=str(align_val) if align_val is not None else None,
        )
        fields_list.append((k, template_field))
    return tuple(fields_list)


def parse_drawing_template(doc: JsonValue) -> DrawingTemplate | IssueReport:
    """Validate and parse a Drawing Template IR document (spec 11.12).

    Runs schema validation first, stopping if schema errors occur. Then runs the 9 semantic
    validation rules and returns a frozen DrawingTemplate or an IssueReport.
    """
    schema_issues = validate_against_schema(doc, TEMPLATE_SCHEMA_ID)
    if schema_issues:
        return build_report(schema_issues)

    assert isinstance(doc, dict)

    raw_id = doc.get("id")
    template_id = str(raw_id) if raw_id is not None else None

    raw_display_name = doc.get("display_name")
    display_name = normalize_text(str(raw_display_name)) if raw_display_name is not None else None

    paper_dict = cast(dict[str, JsonValue], doc["paper"])
    border_dict = cast(dict[str, JsonValue], doc["border"])
    margins = _margins(cast(dict[str, JsonValue], border_dict["margins"]))
    raw_line_width = border_dict.get("line_width")
    border_line_width = float(raw_line_width) if raw_line_width is not None else None  # type: ignore[arg-type]

    title_block_dict = cast(dict[str, JsonValue], doc["title_block"])
    raw_rev = cast(dict[str, JsonValue] | None, doc.get("revision_table"))
    rev_box = _rect(cast(dict[str, JsonValue], raw_rev["box"])) if raw_rev is not None else None

    template = DrawingTemplate(
        id=template_id,
        schema_version=str(doc["schema_version"]),
        display_name=display_name,
        paper_size=str(paper_dict["size"]),
        orientation=str(paper_dict["orientation"]),
        margins=margins,
        border_line_width=border_line_width,
        zones=_parse_zones(title_block_dict),
        lines=_parse_lines(title_block_dict),
        texts=_parse_texts(doc),
        fields=_parse_fields(doc),
        revision_table_box=rev_box,
    )

    issues = semantic_issues(template)
    if issues:
        return build_report(issues)

    return template
