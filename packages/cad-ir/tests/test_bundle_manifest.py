import dataclasses

import pytest
from cad_ir.bundle.manifest import BUNDLE_SCHEMA_ID, BundleManifest, parse_bundle_manifest
from cad_ir.core.issues import IssueReport
from cad_ir.core.json_types import JsonValue
from cad_ir.core.refs import DocumentRef
from cad_ir.generated import ErrorCode


def _manifest(*modules: str, **extra: JsonValue) -> JsonValue:
    return {"bundle_schema_version": "1.0", "modules": list(modules), **extra}


def _report(result: BundleManifest | IssueReport) -> IssueReport:
    assert isinstance(result, IssueReport)
    return result


def test_schema_id() -> None:
    assert BUNDLE_SCHEMA_ID == "https://sw-mcp.invalid/schemas/bundle/v1.json"


def test_spec_example_parses() -> None:
    result = parse_bundle_manifest(
        _manifest("part:bracket@4", "design_intent:BRK-001-DES@2", "drawing_intent:BRK-001-DI@3")
    )
    assert isinstance(result, BundleManifest)
    assert result.bundle_schema_version == "1.0"
    assert len(result.modules) == 3  # noqa: PLR2004
    assert all(isinstance(m, DocumentRef) for m in result.modules)
    assert result.modules[0] == DocumentRef("part", "bracket", 4)
    assert result.modules[0].revision == 4  # noqa: PLR2004
    assert [str(m) for m in result.modules] == [
        "part:bracket@4",
        "design_intent:BRK-001-DES@2",
        "drawing_intent:BRK-001-DI@3",
    ]


def test_floating_ref_is_kept_floating() -> None:
    result = parse_bundle_manifest(_manifest("part:bracket"))
    assert isinstance(result, BundleManifest)
    assert result.modules[0].revision is None


def test_manifest_is_immutable() -> None:
    result = parse_bundle_manifest(_manifest("part:a"))
    assert isinstance(result, BundleManifest)
    assert isinstance(result.modules, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.modules = ()  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_two_drawing_intents_rejected() -> None:
    report = _report(
        parse_bundle_manifest(_manifest("drawing_intent:A@1", "drawing_intent:B@1", "part:p"))
    )
    assert [(i.code, i.pointer, i.ref) for i in report.issues] == [
        (ErrorCode.IR_RULE_VIOLATED, "/modules/1", "drawing_intent:B@1")
    ]
    assert report.has_errors


def test_every_later_duplicate_is_reported() -> None:
    report = _report(
        parse_bundle_manifest(
            _manifest("design_intent:A", "part:p", "design_intent:B", "design_intent:C@2")
        )
    )
    assert [(i.pointer, i.ref) for i in report.issues] == [
        ("/modules/2", "design_intent:B"),
        ("/modules/3", "design_intent:C@2"),
    ]


def test_same_document_with_different_revisions_still_counts_as_duplicate_key() -> None:
    report = _report(parse_bundle_manifest(_manifest("assembly:a@1", "assembly:a@2")))
    assert [i.code for i in report.issues] == [ErrorCode.IR_RULE_VIOLATED]


def test_repeated_part_is_rejected_whatever_the_revision() -> None:
    report = _report(
        parse_bundle_manifest(_manifest("part:a", "assembly:asm", "part:x@4", "part:x"))
    )
    assert [(i.code, i.pointer, i.ref) for i in report.issues] == [
        (ErrorCode.IR_RULE_VIOLATED, "/modules/3", "part:x")
    ]


def test_repeated_part_is_reported_once_even_without_assembly() -> None:
    report = _report(parse_bundle_manifest(_manifest("part:x", "part:x@4")))
    assert [(i.pointer, i.ref) for i in report.issues] == [("/modules/1", "part:x@4")]


def test_repeated_document_with_other_revision_points_at_the_later_entry() -> None:
    report = _report(
        parse_bundle_manifest(_manifest("part:x@4", "assembly:asm", "part:y", "part:x@5"))
    )
    assert [(i.code, i.pointer, i.ref) for i in report.issues] == [
        (ErrorCode.IR_RULE_VIOLATED, "/modules/3", "part:x@5")
    ]


def test_several_drawing_templates_allowed() -> None:
    manifest = parse_bundle_manifest(
        _manifest("drawing_template:A3@1", "drawing_template:A3-CONT@1", "drawing_layout:d")
    )
    assert isinstance(manifest, BundleManifest)
    assert len(manifest.modules) == 3  # noqa: PLR2004


def test_same_drawing_template_twice_rejected() -> None:
    report = parse_bundle_manifest(_manifest("drawing_template:A3@1", "drawing_template:A3@2"))
    assert isinstance(report, IssueReport)
    assert [i.pointer for i in report.issues] == ["/modules/1"]


def test_several_parts_without_assembly_rejected_at_each_extra_part() -> None:
    report = _report(
        parse_bundle_manifest(_manifest("part:a", "drawing_intent:d", "part:b", "part:c@2"))
    )
    assert [(i.code, i.pointer, i.ref) for i in report.issues] == [
        (ErrorCode.IR_RULE_VIOLATED, "/modules/2", "part:b"),
        (ErrorCode.IR_RULE_VIOLATED, "/modules/3", "part:c@2"),
    ]


def test_single_part_without_assembly_allowed() -> None:
    assert isinstance(parse_bundle_manifest(_manifest("part:a")), BundleManifest)


def test_multiple_parts_allowed() -> None:
    result = parse_bundle_manifest(_manifest("part:a@1", "part:b@2", "part:c", "assembly:asm@1"))
    assert isinstance(result, BundleManifest)
    assert len(result.modules) == 4  # noqa: PLR2004


def test_schema_errors_stop_before_semantics() -> None:
    doc = _manifest("drawing_intent:A@1", "drawing_intent:B@1", extra=1)
    report = _report(parse_bundle_manifest(doc))
    assert report.issues
    assert {i.code for i in report.issues} == {ErrorCode.IR_SCHEMA_INVALID}


@pytest.mark.parametrize("doc", [[], "x", None, {"modules": ["part:a"]}, _manifest()])
def test_malformed_documents_give_schema_issues(doc: JsonValue) -> None:
    report = _report(parse_bundle_manifest(doc))
    assert {i.code for i in report.issues} == {ErrorCode.IR_SCHEMA_INVALID}
