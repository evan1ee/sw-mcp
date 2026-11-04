"""D8: the title block is filled, per sheet and title-block mapping (spec 11.5.3).

D8 checks that a field is filled, not that its value is right. The mapping from a sheet format to
its required fields is an input (register K3); nothing here knows where a field sits.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from cad_ir.drawing_template.model import DrawingTemplate

from cad_drawing.checks.outcome import (
    CheckOutcome,
    CheckStatus,
    ReasonCode,
    RuleFailure,
    RuleItem,
    combine_status,
)
from cad_drawing.checks.snapshot import Sheet, Snapshot

MINIMUM_TITLE_FIELDS: tuple[str, ...] = (
    "part_number",
    "revision",
    "material",
    "finish",
    "general_tolerance",
    "scale",
    "projection_symbol",
    "units",
)

_REASON_ORDER: tuple[ReasonCode, ...] = ("title_block_mapping_missing", "title_block_data_missing")


@dataclass(frozen=True, slots=True)
class TitleBlockMapping:
    template: str
    required: tuple[str, ...] = ()
    revision_table: bool = False


def mapping_from_drawing_template(template: DrawingTemplate) -> TitleBlockMapping:
    """Derive a TitleBlockMapping from a DrawingTemplate IR model (ADR-055, K7)."""
    required = tuple(name for name, field in template.fields if field.required)
    return TitleBlockMapping(
        template=template.id or "template",
        required=required,
        revision_table=template.revision_table_box is not None,
    )


def _normal(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip())


def _filled(text: str | None) -> bool:
    return text is not None and bool(text.strip()) and "$PRP" not in text.upper()


def _field_failure(sheet: str, name: str) -> RuleFailure:
    return RuleFailure(
        check="D8",
        sheet=sheet,
        code="title_field_unfilled",
        items=(RuleItem("title_field", name, sheet),),
        detail=(),
        message=f"title block field {name} is empty or an unresolved link",
    )


def _revision_failures(
    sheet: Sheet, mapping: TitleBlockMapping, fields: Mapping[str, str]
) -> list[RuleFailure]:
    if not mapping.revision_table and sheet.revision_table is None:
        return []
    entries = sheet.revision_table.entries if sheet.revision_table else ()
    if not entries:
        return [
            RuleFailure(
                check="D8",
                sheet=sheet.key,
                code="revision_table_missing",
                items=(RuleItem("title_field", "revision_table", sheet.key),),
                detail=(),
                message="the sheet has no revision table entries",
            )
        ]
    revision = fields.get("revision")
    if not _filled(revision):
        return []
    latest, current = _normal(entries[-1]), _normal(revision or "")
    if latest == current:
        return []
    return [
        RuleFailure(
            check="D8",
            sheet=sheet.key,
            code="revision_table_mismatch",
            items=(RuleItem("title_field", "revision", sheet.key),),
            detail=(("latest_entry", latest), ("revision", current)),
            message=f"latest revision table entry {latest!r} differs from revision {current!r}",
        )
    ]


def _sheet_failures(
    sheet: Sheet, mapping: TitleBlockMapping, fields: Mapping[str, str]
) -> list[RuleFailure]:
    required = dict.fromkeys((*MINIMUM_TITLE_FIELDS, *mapping.required))
    failures = [
        _field_failure(sheet.key, n) for n in sorted(required) if not _filled(fields.get(n))
    ]
    return [*failures, *_revision_failures(sheet, mapping, fields)]


def check_d8(snapshot: Snapshot, mappings: Mapping[str, TitleBlockMapping]) -> CheckOutcome:
    statuses: list[CheckStatus] = []
    reasons: set[ReasonCode] = set()
    failures: list[RuleFailure] = []
    for sheet in snapshot.sheets:
        mapping = mappings.get(sheet.sheet_format) if sheet.sheet_format is not None else None
        if mapping is None:
            reasons.add("title_block_mapping_missing")
            statuses.append("not_evaluated")
        elif sheet.title_block_fields is None:
            reasons.add("title_block_data_missing")
            statuses.append("not_evaluated")
        else:
            found = _sheet_failures(sheet, mapping, dict(sheet.title_block_fields))
            failures.extend(found)
            statuses.append("fail" if found else "pass")
    if not snapshot.sheets:
        reasons.add("title_block_data_missing")
        statuses.append("not_evaluated")
    index = {s.key: s.index for s in snapshot.sheets}
    return CheckOutcome(
        status=combine_status(statuses),
        failures=tuple(sorted(failures, key=lambda f: f.sort_key(index))),
        reasons=tuple(r for r in _REASON_ORDER if r in reasons),
    )
