"""Parser and validation driver for Resolved Dimension Scheme (spec 11.10.1)."""

from typing import Any, cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.resolved_scheme.model import (
    RESOLVED_SCHEME_SCHEMA_ID,
    ResolvedScheme,
    SchemeEntry,
)


def parse_resolved_scheme(doc: dict[str, Any]) -> ResolvedScheme | IssueReport:
    """Validate and parse a Resolved Scheme document against schemas/resolved-scheme/v0.json."""
    issues = list(validate_against_schema(cast(JsonValue, doc), RESOLVED_SCHEME_SCHEMA_ID))
    if issues:
        return build_report(issues)

    entries: dict[str, SchemeEntry] = {}
    for entry_id, e_dict in doc.get("entries", {}).items():
        entries[entry_id] = SchemeEntry(
            kind=str(e_dict["kind"]),
            source=str(e_dict["source"]),
            status=str(e_dict["status"]),
            origin=str(e_dict["origin"]),
            covers=tuple(str(c) for c in e_dict.get("covers", [])),
            measures=e_dict.get("measures"),
            tolerance=e_dict.get("tolerance"),
            reason=e_dict.get("reason"),
            auxiliary=bool(e_dict.get("auxiliary", False)),
        )

    return ResolvedScheme(
        schema_version=str(doc["schema_version"]),
        drawing_intent=str(doc["drawing_intent"]),
        entries=entries,
        part_revision=doc.get("part_revision"),
        pipeline_version=doc.get("pipeline_version"),
    )
