"""The error catalogue (ADR-037) matches the decision record and the docs."""

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ERRORS: dict[str, Any] = json.loads(
    (ROOT / "schemas" / "common" / "errors.json").read_text(encoding="utf-8")
)

ADR_037_CODES = [
    "IR_SCHEMA_INVALID",
    "IR_SCHEMA_VERSION_UNSUPPORTED",
    "IR_REFERENCE_UNRESOLVED",
    "IR_MODULE_MISSING",
    "IR_RULE_VIOLATED",
    "IR_CYCLE",
    "REV_CONFLICT",
    "REF_AMBIGUOUS",
    "REF_NOT_FOUND",
    "REF_SIGNATURE_MISMATCH",
    "REF_NOT_IN_VIEW",
    "REF_LOW_CONFIDENCE",
    "COMPILE_FAILED",
    "COMPILE_UNSUPPORTED_FEATURE",
    "COMPILE_PLAN_INVALID",
    "EXEC_TIMEOUT",
    "EXEC_CANCELLED",
    "EXEC_INTERRUPTED",
    "EXEC_INTERRUPTED_BY_USER",
    "EXEC_NOT_FOUND",
    "EXEC_DOCUMENT_DIRTY",
    "DUPLICATE_OPERATION",
    "BACKEND_LOST",
    "BACKEND_BUSY",
    "BACKEND_UI_BLOCKED",
    "BACKEND_REBUILD_ERROR",
    "BACKEND_READ_ONLY",
    "BACKEND_SESSION_AMBIGUOUS",
    "BACKEND_VERSION_UNSUPPORTED",
    "BACKEND_CAPABILITY_MISSING",
    "DRAWING_CHECK_FAILED",
    "DRAWING_RELAYOUT_EXHAUSTED",
    "DRAWING_UNSUPPORTED_PART",
    "AUTH_SOURCE_WRITE_NOT_ALLOWED",
    "AUTH_PATH_DENIED",
    "STORE_LOCKED",
    "STORE_CORRUPT",
    "CONFIG_INVALID",
    "FILE_NOT_FOUND",
    "STORE_UNAVAILABLE",
    "PART_VERIFICATION_FAILED",
]

EXPECTED_CODE_COUNT = 41
# Timeouts, interruptions and a lost add-in connection are after_fix: the operation may have run.
SAFE = {
    "BACKEND_BUSY",
    "BACKEND_UI_BLOCKED",
    "STORE_LOCKED",
}
NEVER_EXPLICIT = {
    "COMPILE_UNSUPPORTED_FEATURE",
    "BACKEND_CAPABILITY_MISSING",
    "BACKEND_READ_ONLY",
    "EXEC_NOT_FOUND",
    "EXEC_CANCELLED",
    "EXEC_INTERRUPTED_BY_USER",
    "DUPLICATE_OPERATION",
    "STORE_CORRUPT",
    "DRAWING_UNSUPPORTED_PART",
}
CODE_MENTION = re.compile(
    r"\b(?:IR|REV|REF|COMPILE|EXEC|BACKEND|DRAWING|AUTH|STORE|CONFIG|FILE)_[A-Z0-9_]+\b"
    r"|\bDUPLICATE_OPERATION\b"
    r"|\bPART_VERIFICATION_FAILED\b"
)


def _branches() -> list[dict[str, Any]]:
    return ERRORS["oneOf"]


def _expected_retryable(code: str) -> str:
    if code in SAFE:
        return "safe"
    if code.startswith("AUTH_") or code.endswith("_UNSUPPORTED") or code in NEVER_EXPLICIT:
        return "never"
    return "after_fix"


def test_catalogue_matches_adr_037() -> None:
    assert len(ADR_037_CODES) == EXPECTED_CODE_COUNT
    assert [b["const"] for b in _branches()] == ADR_037_CODES
    assert ERRORS["type"] == "string"


def test_docs_mention_only_catalogued_codes() -> None:
    catalogue = set(ADR_037_CODES)
    mentioned: dict[str, set[str]] = {}
    for path in sorted((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in CODE_MENTION.finditer(text):
            mentioned.setdefault(match.group(0), set()).add(path.relative_to(ROOT).as_posix())
    unknown = {code: sorted(files) for code, files in mentioned.items() if code not in catalogue}
    assert unknown == {}


def test_every_code_has_retryable_and_description() -> None:
    for branch in _branches():
        assert set(branch) == {"const", "description", "x-retryable"}, branch["const"]
        assert branch["x-retryable"] in {"never", "after_fix", "safe"}
        assert branch["description"].strip()
        assert "\n" not in branch["description"]


def test_default_retryable_values() -> None:
    actual = {b["const"]: b["x-retryable"] for b in _branches()}
    assert actual == {code: _expected_retryable(code) for code in ADR_037_CODES}


def test_drawing_check_failed_is_a_result_not_a_tool_error() -> None:
    by_code = {b["const"]: b for b in _branches()}
    description = by_code["DRAWING_CHECK_FAILED"]["description"]
    assert "could not be completed" not in description
    assert "a failed check is a result, not a tool error" in description


def test_may_have_run_codes_are_after_fix() -> None:
    by_code = {b["const"]: b["x-retryable"] for b in _branches()}
    for code in ("EXEC_TIMEOUT", "EXEC_INTERRUPTED", "BACKEND_LOST"):
        assert by_code[code] == "after_fix"
