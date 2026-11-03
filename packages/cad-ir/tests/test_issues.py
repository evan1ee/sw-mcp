import dataclasses

import pytest
from cad_ir.core.issues import (
    MAX_REPORTED_ISSUES,
    IssueReport,
    ValidationIssue,
    build_report,
)
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated import ErrorCode

ISSUE_SCHEMA = "https://sw-mcp.invalid/schemas/common/v0.json#/$defs/ValidationIssue"


def _issue(
    pointer: str, code: ErrorCode = ErrorCode.IR_SCHEMA_INVALID, msg: str = "m"
) -> ValidationIssue:
    return ValidationIssue(code=code, pointer=pointer, message=msg)


def test_max_reported_issues_is_fifty() -> None:
    assert MAX_REPORTED_ISSUES == 50  # noqa: PLR2004


def test_build_report_orders_and_caps() -> None:
    issues = [_issue(f"/items/{i}") for i in reversed(range(60))]
    report = build_report(issues)
    assert [i.pointer for i in report.issues] == [f"/items/{i}" for i in range(50)]
    assert report.omitted == 10  # noqa: PLR2004
    assert isinstance(report.issues, tuple)


def test_pointers_compare_token_wise_with_numeric_indices() -> None:
    pointers = [
        "/modules/10",
        "/modules/2",
        "/modules/1",
        "/modules",
        "",
        "/modules/a",
        "/modules/02",
    ]
    ordered = [i.pointer for i in build_report(_issue(p) for p in pointers).issues]
    assert ordered == [
        "",
        "/modules",
        "/modules/1",
        "/modules/2",
        "/modules/10",
        "/modules/02",
        "/modules/a",
    ]


def test_pointer_tokens_are_decoded_before_comparison() -> None:
    # "a/b" is the token "~1" encoded; "a" < "a/b" by code point regardless of the escape
    ordered = [
        i.pointer for i in build_report([_issue("/a~1b"), _issue("/a"), _issue("/a0")]).issues
    ]
    assert ordered == ["/a", "/a~1b", "/a0"]


def test_report_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError, match="omitted_errors"):
        IssueReport(issues=(), omitted=1, omitted_errors=2)
    with pytest.raises(ValueError, match="omitted_errors"):
        IssueReport(issues=(), omitted=0, omitted_errors=-1)


def test_build_report_sorts_by_pointer_then_code_then_message() -> None:
    a = _issue("/a", ErrorCode.IR_SCHEMA_INVALID, "z")
    b = _issue("/a", ErrorCode.IR_SCHEMA_INVALID, "b")
    c = _issue("/a", ErrorCode.IR_CYCLE, "a")
    d = _issue("", ErrorCode.REV_CONFLICT, "a")
    assert build_report([a, b, c, d]).issues == (d, c, b, a)  # IR_CYCLE < IR_SCHEMA_INVALID


def test_build_report_deterministic() -> None:
    issues = [_issue(f"/x/{i}", msg=str(i)) for i in range(70)]
    assert build_report(issues) == build_report(reversed(issues))
    assert build_report([]) == IssueReport(issues=(), omitted=0, omitted_errors=0)


def test_report_has_errors_ignores_warnings() -> None:
    warning = ValidationIssue(ErrorCode.IR_RULE_VIOLATED, "/w", "w", severity="warning")
    assert not build_report([warning]).has_errors
    assert build_report([warning, _issue("/e")]).has_errors
    assert not build_report([]).has_errors


def test_has_errors_counts_errors_beyond_the_cap() -> None:
    warnings = [
        ValidationIssue(ErrorCode.IR_RULE_VIOLATED, f"/a/{i}", "w", severity="warning")
        for i in range(60)
    ]
    report = build_report([*warnings, _issue("/z")])
    assert report.omitted == 11  # noqa: PLR2004
    assert report.has_errors  # the only error is among the omitted ones


def test_issue_to_json_omits_defaults() -> None:
    assert _issue("/a").to_json() == {
        "code": "IR_SCHEMA_INVALID",
        "pointer": "/a",
        "message": "m",
    }


def test_issue_to_json_full() -> None:
    issue = ValidationIssue(
        ErrorCode.IR_REFERENCE_UNRESOLVED,
        "/nodes/bore_1",
        "msg",
        severity="warning",
        expected=("a", "b"),
        ref="bore_1.x",
        patch_op=0,
    )
    assert issue.to_json() == {
        "code": "IR_REFERENCE_UNRESOLVED",
        "pointer": "/nodes/bore_1",
        "message": "msg",
        "severity": "warning",
        "expected": ["a", "b"],
        "ref": "bore_1.x",
        "patch_op": 0,
    }


@pytest.mark.parametrize(
    "issue",
    [
        _issue(""),
        ValidationIssue(ErrorCode.IR_CYCLE, "/a", "m", "warning", ("x",), "r", 3),
        ValidationIssue(ErrorCode.REV_CONFLICT, "/a", "m", expected=()),
    ],
)
def test_issue_to_json_matches_schema(issue: ValidationIssue) -> None:
    assert validate_against_schema(issue.to_json(), ISSUE_SCHEMA) == ()


def test_issue_is_immutable() -> None:
    issue = _issue("/a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        issue.pointer = "/b"  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]


def test_omitted_warnings_do_not_make_errors() -> None:
    warnings = [
        ValidationIssue(ErrorCode.IR_RULE_VIOLATED, f"/a/{i}", "w", severity="warning")
        for i in range(60)
    ]
    report = build_report(warnings)
    assert report.omitted == 10  # noqa: PLR2004
    assert not report.has_errors
