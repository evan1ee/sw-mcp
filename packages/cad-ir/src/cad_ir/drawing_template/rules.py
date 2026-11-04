"""Semantic validation rules for Drawing Template IR (spec 11.12)."""

from typing import Final

from cad_ir.core.issues import ValidationIssue, pointer_sort_key
from cad_ir.core.numbers import values_equal
from cad_ir.drawing_template.model import (
    DrawingTemplate,
    Rect,
)
from cad_ir.generated import ErrorCode

TEMPLATE_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/drawing-template/v0.json"

MINIMUM_FIELDS: Final[tuple[str, ...]] = (
    "part_number",
    "revision",
    "material",
    "finish",
    "general_tolerance",
    "scale",
    "projection_symbol",
    "units",
)


def _le(a: float, b: float) -> bool:
    """True if a <= b within the length quantum."""
    return a <= b or values_equal(a, b, "length", "mm")


def _ge(a: float, b: float) -> bool:
    """True if a >= b within the length quantum."""
    return a >= b or values_equal(a, b, "length", "mm")


def _rect_is_inverted(r: Rect) -> bool:
    """True if min is not strictly less than max on either axis."""
    return _le(r.max_x, r.min_x) or _le(r.max_y, r.min_y)


def _rect_contains(outer: Rect, inner: Rect) -> bool:
    """True if outer contains inner within quantum tolerances."""
    return (
        _le(outer.min_x, inner.min_x)
        and _ge(outer.max_x, inner.max_x)
        and _le(outer.min_y, inner.min_y)
        and _ge(outer.max_y, inner.max_y)
    )


def _point_in_rect(rect: Rect, p: tuple[float, float]) -> bool:
    """True if 2D point p is within rect within quantum tolerances."""
    return (
        _le(rect.min_x, p[0])
        and _ge(rect.max_x, p[0])
        and _le(rect.min_y, p[1])
        and _ge(rect.max_y, p[1])
    )


def _rects_overlap(r1: Rect, r2: Rect) -> bool:
    """True if r1 and r2 overlap in 2D by more than the quantum. Touching edges pass."""
    overlap_min_x = max(r1.min_x, r2.min_x)
    overlap_max_x = min(r1.max_x, r2.max_x)
    if _le(overlap_max_x, overlap_min_x) or values_equal(
        overlap_max_x, overlap_min_x, "length", "mm"
    ):
        return False

    overlap_min_y = max(r1.min_y, r2.min_y)
    overlap_max_y = min(r1.max_y, r2.max_y)
    return not (
        _le(overlap_max_y, overlap_min_y)
        or values_equal(overlap_max_y, overlap_min_y, "length", "mm")
    )


def _source_rank(source: str) -> int:
    if source.startswith("design_intent:"):
        return 0
    if source.startswith("drawing_intent:"):
        return 1
    return 2


def _rule_paper(template: DrawingTemplate, issues: list[ValidationIssue]) -> bool:
    if template.paper_size == "A4" and template.orientation != "portrait":
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/paper/orientation",
                message="A4 paper must use portrait orientation (ISO 5457)",
            )
        )
        return False
    if template.paper_size in ("A3", "A2", "A1", "A0") and template.orientation != "landscape":
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/paper/orientation",
                message=f"{template.paper_size} paper must use landscape orientation (ISO 5457)",
            )
        )
        return False
    return True


def _rule_border(template: DrawingTemplate, issues: list[ValidationIssue]) -> bool:
    border_rect = template.border_rect
    if _le(border_rect.width, 0.0) or _le(border_rect.height, 0.0):
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/border/margins",
                message="margins leave non-positive border area on sheet",
            )
        )
        return False
    return True


def _validate_rectangles(
    template: DrawingTemplate, issues: list[ValidationIssue]
) -> tuple[
    list[tuple[str, Rect]],
    list[tuple[str, Rect]],
    list[tuple[str, Rect]],
    Rect | None,
    set[str],
    set[str],
    bool,
]:
    valid_zones: list[tuple[str, Rect]] = []
    has_inverted_zone = False
    for key, zone_rect in template.zones:
        if _rect_is_inverted(zone_rect):
            has_inverted_zone = True
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/title_block/zones/{key}",
                    message="zone rectangle min coordinates must be strictly less than max",
                )
            )
        else:
            valid_zones.append((key, zone_rect))

    valid_text_boxes: list[tuple[str, Rect]] = []
    inverted_text_keys: set[str] = set()
    for key, static_text in template.texts:
        if _rect_is_inverted(static_text.box):
            inverted_text_keys.add(key)
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/texts/{key}/box",
                    message="text box min coordinates must be strictly less than max",
                )
            )
        else:
            valid_text_boxes.append((key, static_text.box))

    valid_field_boxes: list[tuple[str, Rect]] = []
    inverted_field_keys: set[str] = set()
    for key, field in template.fields:
        if _rect_is_inverted(field.box):
            inverted_field_keys.add(key)
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/fields/{key}/box",
                    message="field box min coordinates must be strictly less than max",
                )
            )
        else:
            valid_field_boxes.append((key, field.box))

    valid_rev_box: Rect | None = None
    if template.revision_table_box is not None:
        if _rect_is_inverted(template.revision_table_box):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer="/revision_table/box",
                    message="revision table box min coordinates must be strictly less than max",
                )
            )
        else:
            valid_rev_box = template.revision_table_box

    return (
        valid_zones,
        valid_text_boxes,
        valid_field_boxes,
        valid_rev_box,
        inverted_text_keys,
        inverted_field_keys,
        has_inverted_zone,
    )


def _rule_zones(
    template: DrawingTemplate,
    valid_zones: list[tuple[str, Rect]],
    skip_border: bool,
    issues: list[ValidationIssue],
) -> None:
    if not template.zones:
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/title_block/zones",
                message="at least one title block zone must be defined",
            )
        )

    if not skip_border:
        border_rect = template.border_rect
        for key, zone_rect in valid_zones:
            if not _rect_contains(border_rect, zone_rect):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/title_block/zones/{key}",
                        message=f"title block zone '{key}' must lie inside the border",
                    )
                )

    for i, (k1, z1) in enumerate(valid_zones):
        for k2, z2 in valid_zones[i + 1 :]:
            if _rects_overlap(z1, z2):
                later_key = max(k1, k2)
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/title_block/zones/{later_key}",
                        message=f"title block zone '{later_key}' overlaps with another zone",
                    )
                )


def _rule_lines(
    template: DrawingTemplate,
    valid_zones: list[tuple[str, Rect]],
    skip_containment: bool,
    issues: list[ValidationIssue],
) -> None:
    for key, line in template.lines:
        is_zero_len = values_equal(line.start[0], line.end[0], "length", "mm") and values_equal(
            line.start[1], line.end[1], "length", "mm"
        )
        if is_zero_len:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/title_block/lines/{key}",
                    message="title block line must have non-zero length",
                )
            )
        elif not skip_containment:
            in_zone = any(
                _point_in_rect(zone, line.start) and _point_in_rect(zone, line.end)
                for _, zone in valid_zones
            )
            if not in_zone:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/title_block/lines/{key}",
                        message=f"title block line '{key}' must lie within one zone",
                    )
                )


def _rule_text_box_containment(
    border_rect: Rect,
    valid_text_boxes: list[tuple[str, Rect]],
    issues: list[ValidationIssue],
) -> None:
    for key, box in valid_text_boxes:
        if not _rect_contains(border_rect, box):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/texts/{key}/box",
                    message=f"text box '{key}' must lie inside the border",
                )
            )


def _rule_zone_box_containment(
    valid_zones: list[tuple[str, Rect]],
    valid_field_boxes: list[tuple[str, Rect]],
    valid_rev_box: Rect | None,
    issues: list[ValidationIssue],
) -> None:
    for key, box in valid_field_boxes:
        if not any(_rect_contains(zone, box) for _, zone in valid_zones):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/fields/{key}/box",
                    message=f"field box '{key}' must lie entirely within one title block zone",
                )
            )

    if valid_rev_box is not None and not any(
        _rect_contains(zone, valid_rev_box) for _, zone in valid_zones
    ):
        issues.append(
            ValidationIssue(
                code=ErrorCode.IR_RULE_VIOLATED,
                pointer="/revision_table/box",
                message="revision table box must lie entirely within one title block zone",
            )
        )


def _rule_box_overlaps(
    all_boxes: list[tuple[str, Rect]],
    issues: list[ValidationIssue],
) -> None:
    for i, (ptr1, box1) in enumerate(all_boxes):
        for ptr2, box2 in all_boxes[i + 1 :]:
            if _rects_overlap(box1, box2):
                later_ptr = ptr2 if pointer_sort_key(ptr2) > pointer_sort_key(ptr1) else ptr1
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=later_ptr,
                        message=f"box at '{later_ptr}' overlaps with another box",
                    )
                )


def _rule_text_height(
    template: DrawingTemplate,
    inverted_text_keys: set[str],
    inverted_field_keys: set[str],
    issues: list[ValidationIssue],
) -> None:
    for key, static_text in template.texts:
        if key not in inverted_text_keys and not _le(static_text.height, static_text.box.height):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/texts/{key}/height",
                    message=f"text height ({static_text.height} mm) exceeds box height",
                )
            )

    for key, field in template.fields:
        if key not in inverted_field_keys and not _le(field.height, field.box.height):
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/fields/{key}/height",
                    message=f"field text height ({field.height} mm) exceeds box height",
                )
            )


def _rule_minimum_fields(template: DrawingTemplate, issues: list[ValidationIssue]) -> None:
    fields_dict = dict(template.fields)
    for req_field in MINIMUM_FIELDS:
        if req_field not in fields_dict:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer="/fields",
                    message=f"minimum required field '{req_field}' is missing",
                )
            )
        elif not fields_dict[req_field].required:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/fields/{req_field}/required",
                    message=f"minimum required field '{req_field}' cannot set required to false",
                )
            )


def _rule_source_order(template: DrawingTemplate, issues: list[ValidationIssue]) -> None:
    for key, field in template.fields:
        has_sheet = any(s.startswith("sheet:") for s in field.source)
        if has_sheet and len(field.source) != 1:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.IR_RULE_VIOLATED,
                    pointer=f"/fields/{key}/source",
                    message="sheet property source must be the sole candidate",
                )
            )
        else:
            ranks = [_source_rank(s) for s in field.source]
            if ranks != sorted(ranks):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.IR_RULE_VIOLATED,
                        pointer=f"/fields/{key}/source",
                        message="candidate sources must follow ownership order",
                    )
                )


def semantic_issues(template: DrawingTemplate) -> list[ValidationIssue]:
    """Evaluate the 9 semantic validation rules of spec 11.12."""
    issues: list[ValidationIssue] = []

    paper_ok = _rule_paper(template, issues)
    border_ok = _rule_border(template, issues)
    skip_border = not (paper_ok and border_ok)

    (
        valid_zones,
        valid_text_boxes,
        valid_field_boxes,
        valid_rev_box,
        inverted_text_keys,
        inverted_field_keys,
        has_inverted_zone,
    ) = _validate_rectangles(template, issues)

    _rule_zones(template, valid_zones, skip_border, issues)

    skip_containment = has_inverted_zone or not valid_zones
    _rule_lines(template, valid_zones, skip_containment, issues)

    if not skip_border:
        _rule_text_box_containment(template.border_rect, valid_text_boxes, issues)

    if not skip_containment:
        _rule_zone_box_containment(valid_zones, valid_field_boxes, valid_rev_box, issues)

    all_boxes: list[tuple[str, Rect]] = []
    for key, box in valid_text_boxes:
        all_boxes.append((f"/texts/{key}/box", box))
    for key, box in valid_field_boxes:
        all_boxes.append((f"/fields/{key}/box", box))
    if valid_rev_box is not None:
        all_boxes.append(("/revision_table/box", valid_rev_box))

    _rule_box_overlaps(all_boxes, issues)

    _rule_text_height(template, inverted_text_keys, inverted_field_keys, issues)
    _rule_minimum_fields(template, issues)
    _rule_source_order(template, issues)

    return issues
