"""IR bundle manifest validation (spec 3.4.5)."""

from dataclasses import dataclass
from typing import Final

from cad_ir.core.issues import IssueReport, ValidationIssue, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.pointer import json_pointer
from cad_ir.core.refs import DocumentRef, parse_document_ref
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated import ErrorCode

BUNDLE_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/bundle/v1.json"


@dataclass(frozen=True, slots=True)
class BundleManifest:
    """A schema-valid, semantically valid manifest. Floating references stay floating."""

    bundle_schema_version: str
    modules: tuple[DocumentRef, ...]


def _violation(index: int, ref: DocumentRef, message: str) -> ValidationIssue:
    return ValidationIssue(
        code=ErrorCode.IR_RULE_VIOLATED,
        pointer=json_pointer("modules", index),
        message=message,
        ref=str(ref),
    )


def _semantic_issues(modules: tuple[DocumentRef, ...]) -> list[ValidationIssue]:
    """Bundle rules (spec 3.4.5), one issue per offending entry.

    A document (module and ID, whatever the revision) is listed once. Other than ``part``, a
    module key is listed once; several parts need an ``assembly`` in the bundle.
    """
    has_assembly = any(ref.module == "assembly" for ref in modules)
    seen_documents: set[tuple[str, str]] = set()
    seen_modules: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, ref in enumerate(modules):
        document = (ref.module, ref.document_id)
        if document in seen_documents:
            message = f"{ref.module}:{ref.document_id} is listed more than once"
        elif ref.module != "part" and ref.module in seen_modules:
            message = f"at most one {ref.module} document is allowed in a bundle"
        elif ref.module == "part" and not has_assembly and "part" in seen_modules:
            message = "more than one part needs an assembly in the bundle"
        else:
            message = ""
        if message:
            issues.append(_violation(index, ref, message))
        seen_documents.add(document)
        seen_modules.add(ref.module)
    return issues


def parse_bundle_manifest(doc: JsonValue) -> BundleManifest | IssueReport:
    """Validate a bundle manifest: schema first, then the semantic rules.

    Schema issues stop the pipeline (spec 3.4.7). Resolving floating references needs the
    project store and is not done here.
    """
    schema_issues = validate_against_schema(doc, BUNDLE_SCHEMA_ID)
    if schema_issues:
        return build_report(schema_issues)

    assert isinstance(doc, dict)
    version = doc["bundle_schema_version"]
    raw_modules = doc["modules"]
    assert isinstance(version, str)
    assert isinstance(raw_modules, list)
    modules = tuple(parse_document_ref(str(item)) for item in raw_modules)

    issues = _semantic_issues(modules)
    if issues:
        return build_report(issues)
    return BundleManifest(bundle_schema_version=version, modules=modules)
