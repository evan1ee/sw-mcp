"""Unit tests for Drawing Intent IR (spec 11.10)."""

import json
from pathlib import Path
from typing import Any

from cad_ir.core.issues import IssueReport
from cad_ir.drawing_intent import (
    INTENT_SCHEMA_ID,
    CriticalDimension,
    DatumFeature,
    DrawingIntent,
    GDTCallout,
    IntentContext,
    SurfaceFinish,
    parse_drawing_intent,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "schemas" / "drawing-intent"
EXPECTED_DATUMS_COUNT = 2
EXPECTED_CRITICAL_DIMS_COUNT = 2
EXPECTED_RA = 0.8
EXPECTED_GDT_TOL = 0.02


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_intent_schema_id_constant() -> None:
    assert INTENT_SCHEMA_ID == "https://sw-mcp.invalid/schemas/drawing-intent/v0.json"


def test_valid_minimal_intent_parses() -> None:
    doc = _load(FIXTURES_DIR / "valid" / "minimal.json")
    res = parse_drawing_intent(doc)
    assert isinstance(res, DrawingIntent)
    assert res.id == "BRK-001-DI"
    assert res.schema_version == "0.1"
    assert res.units == "mm"
    assert res.documents == "part:bracket@4"
    assert res.design_intent == "design_intent:BRK-001-DES@2"
    assert res.configuration == "Default"
    assert res.general_tolerance == "ISO 2768-m"

    assert isinstance(res.surface_finish, SurfaceFinish)
    assert res.surface_finish.general == {"ra": 1.6}
    assert "finish_bore" in res.surface_finish.exceptions
    exc = res.surface_finish.exceptions["finish_bore"]
    assert exc["target"] == "bore_1.cylindrical_face"
    assert exc["ra"] == EXPECTED_RA
    assert exc["requirement"] == "r1"

    assert len(res.datums) == EXPECTED_DATUMS_COUNT
    assert isinstance(res.datums["A"], DatumFeature)
    assert res.datums["A"].ref == "base_extrude.bottom_face"
    assert res.datums["A"].applies_to == "surface"
    assert res.datums["B"].applies_to == "feature_of_size"

    assert len(res.critical_dimensions) == EXPECTED_CRITICAL_DIMS_COUNT
    cd = res.critical_dimensions["bore_dia"]
    assert isinstance(cd, CriticalDimension)
    assert cd.param == "bore_1.diameter"
    assert cd.tolerance == {"type": "fit", "value": "H7"}
    assert cd.requirement == "r1"

    assert len(res.gdt) == 1
    g = res.gdt["perp_bore"]
    assert isinstance(g, GDTCallout)
    assert g.characteristic == "perpendicularity"
    assert g.tolerance == EXPECTED_GDT_TOL
    assert g.target == "bore_1.cylindrical_face"
    assert g.applies_to == "feature_of_size"
    assert g.datums == ("A",)

    # Roundtrip
    d = res.to_dict()
    assert d["id"] == "BRK-001-DI"
    assert d["module"] == "drawing_intent"


def test_invalid_intent_returns_issue_report() -> None:
    doc = _load(FIXTURES_DIR / "invalid" / "missing_id.json")
    res = parse_drawing_intent(doc)
    assert isinstance(res, IssueReport)


def test_intent_context_roundtrip() -> None:
    ctx = IntentContext(
        process="machined",
        material="AL 6061-T6",
        treatment="Anodize",
        metadata={"part_number": "BRK-001"},
    )
    d = ctx.to_dict()
    assert d["process"] == "machined"
    assert d["metadata"]["part_number"] == "BRK-001"
