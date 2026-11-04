"""Outcome records and status combination (spec 11.5.3)."""

from cad_drawing.checks.outcome import (
    CheckOutcome,
    CheckStatus,
    CheckWarning,
    RuleFailure,
    RuleItem,
    combine_status,
)


def test_combine_status_order() -> None:
    assert combine_status(["pass", "not_evaluated", "fail"]) == "fail"
    assert combine_status(["pass", "not_evaluated"]) == "not_evaluated"
    assert combine_status(["pass", "pass"]) == "pass"
    assert combine_status([]) == "pass"
    statuses: tuple[CheckStatus, ...] = ("not_evaluated", "fail")
    assert combine_status(iter(statuses)) == "fail"


def test_rule_item_json_omits_nothing() -> None:
    assert RuleItem("annotation", "a1", None).to_json() == {
        "kind": "annotation",
        "id": "a1",
        "sheet": None,
    }


def test_rule_failure_json_and_sort_key() -> None:
    failure = RuleFailure(
        "D8",
        "s_1",
        "title_field_unfilled",
        (RuleItem("title_field", "material", "s_1"),),
        (("k", "v"),),
        "msg",
    )
    assert failure.to_json() == {
        "check": "D8",
        "sheet": "s_1",
        "code": "title_field_unfilled",
        "items": [{"kind": "title_field", "id": "material", "sheet": "s_1"}],
        "detail": {"k": "v"},
        "message": "msg",
    }
    document = RuleFailure("D10", None, "reopen_failed", (), (), "m")
    assert document.sort_key({"s_1": 0})[0] == -1
    assert failure.sort_key({"s_1": 3})[:2] == (3, 8)


def test_warning_json_and_outcome_defaults() -> None:
    assert CheckWarning("silhouette_attachment", "s", "a", "m").to_json() == {
        "code": "silhouette_attachment",
        "sheet": "s",
        "annotation": "a",
        "message": "m",
    }
    outcome = CheckOutcome("pass")
    assert (outcome.failures, outcome.reasons, outcome.warnings, outcome.parts) == ((), (), (), ())
