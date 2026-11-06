"""Unit tests for Resolved Dimension Scheme (spec 11.10.1)."""

import json
from pathlib import Path
from typing import Any

from cad_ir.core.issues import IssueReport
from cad_ir.resolved_scheme import (
    RESOLVED_SCHEME_SCHEMA_ID,
    ResolvedScheme,
    SchemeEntry,
    parse_resolved_scheme,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "schemas" / "resolved-scheme"
EXPECTED_ENTRIES_COUNT = 3


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_scheme_schema_id_constant() -> None:
    assert RESOLVED_SCHEME_SCHEMA_ID == "https://sw-mcp.invalid/schemas/resolved-scheme/v0.json"


def test_valid_minimal_scheme_parses() -> None:
    doc = _load(FIXTURES_DIR / "valid" / "minimal.json")
    res = parse_resolved_scheme(doc)
    assert isinstance(res, ResolvedScheme)
    assert res.schema_version == "0.1"
    assert res.drawing_intent == "drawing_intent:BRK-001-DI@1"
    assert res.part_revision == 1
    assert res.pipeline_version == "1.0"
    assert len(res.entries) == EXPECTED_ENTRIES_COUNT

    e1 = res.entries["ds_bore_1_diameter_b41219"]
    assert isinstance(e1, SchemeEntry)
    assert e1.kind == "diameter"
    assert e1.covers == ("bore_1.diameter",)
    assert e1.source == "model_item"
    assert e1.tolerance == {"critical": "bore_dia"}
    assert e1.status == "shown"
    assert e1.origin == "derived"
    assert e1.auxiliary is False

    e2 = res.entries["ds_sketch_bore_x_4556c0"]
    assert isinstance(e2, SchemeEntry)
    assert e2.kind == "linear"
    assert e2.measures == {"from": "plane:right", "to": "bore_1.axis"}
    assert e2.source == "reference"
    assert e2.tolerance == "general"
    assert e2.status == "shown"

    e3 = res.entries["ds_sketch_bore_x_be93d5"]
    assert isinstance(e3, SchemeEntry)
    assert e3.status == "hidden"
    assert e3.reason == "replaced_by:ds_sketch_bore_x_4556c0"

    # Roundtrip
    d = res.to_dict()
    assert d["drawing_intent"] == "drawing_intent:BRK-001-DI@1"
    assert len(d["entries"]) == EXPECTED_ENTRIES_COUNT


def test_invalid_scheme_returns_issue_report() -> None:
    doc = _load(FIXTURES_DIR / "invalid" / "missing_entries.json")
    res = parse_resolved_scheme(doc)
    assert isinstance(res, IssueReport)
