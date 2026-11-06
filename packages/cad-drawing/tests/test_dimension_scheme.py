"""Unit tests for dimension scheme resolution and duplicate cleanup (spec 11.4, 11.10.1)."""

from cad_drawing.checks.snapshot import (
    Annotation,
    PolylineCurve,
    Rect,
    Sheet,
    Snapshot,
)
from cad_drawing.dimension_scheme import (
    DuplicatePlan,
    HideAction,
    apply_cleanup_to_scheme,
    plan_duplicate_cleanup,
    resolve_scheme_from_snapshot,
)
from cad_ir.drawing_intent import CriticalDimension, DrawingIntent
from cad_ir.resolved_scheme import ResolvedScheme

EXPECTED_KEPT_COUNT = 2
EXPECTED_ENTRIES_COUNT = 2


def _make_sample_snapshot(duplicate: bool = False) -> Snapshot:
    ann1 = Annotation(
        key="a1",
        kind="dimension",
        native_id="D1@Sketch1",
        tag=None,
        view="v_front",
        attachments=(),
        dimension_lines=(PolylineCurve(points=((100.0, 100.0), (120.0, 100.0))),),
        extension_lines=(),
        arrowheads=(),
        leaders=(),
        text_boxes=(),
        parameters=("bore_1.diameter",),
    )
    ann2_params = ("bore_1.diameter",) if duplicate else ("bracket.width",)
    ann2 = Annotation(
        key="a2",
        kind="dimension",
        native_id="D1@Sketch1_dup" if duplicate else "D2@Sketch1",
        tag=None,
        view="v_top",
        attachments=(),
        dimension_lines=(PolylineCurve(points=((100.0, 200.0), (120.0, 200.0))),),
        extension_lines=(),
        arrowheads=(),
        leaders=(),
        text_boxes=(),
        parameters=ann2_params,
    )
    sheet = Sheet(
        index=1,
        key="s1",
        native_id="Sheet1",
        size_mm=(420.0, 297.0),
        border=Rect((10.0, 10.0), (410.0, 287.0)),
        title_block=(Rect((250.0, 10.0), (410.0, 70.0)),),
        views=(),
        annotations=(ann1, ann2),
    )
    return Snapshot(
        schema_version="0.1",
        document="bracket.slddrw",
        revision=1,
        solidworks_version="2025",
        service_pack="SP0.1",
        captured_at="2026-11-05T00:00:00Z",
        sheets=(sheet,),
    )


def test_plan_duplicate_cleanup_no_duplicates() -> None:
    snapshot = _make_sample_snapshot(duplicate=False)
    plan = plan_duplicate_cleanup(snapshot)
    assert isinstance(plan, DuplicatePlan)
    assert len(plan.to_hide) == 0
    assert len(plan.to_keep) == EXPECTED_KEPT_COUNT


def test_plan_duplicate_cleanup_with_duplicate() -> None:
    snapshot = _make_sample_snapshot(duplicate=True)
    plan = plan_duplicate_cleanup(snapshot)
    assert isinstance(plan, DuplicatePlan)
    assert len(plan.to_hide) == 1
    # ann1 (v_front) kept as primary, ann2 hidden
    assert plan.to_hide[0].native_id == "D1@Sketch1_dup"
    assert plan.to_hide[0].reason == "duplicate"
    assert len(plan.to_keep) == 1
    assert plan.to_keep[0] == "D1@Sketch1"


def test_resolve_scheme_from_snapshot() -> None:
    snapshot = _make_sample_snapshot(duplicate=False)
    intent = DrawingIntent(
        id="BRK-001-DI",
        schema_version="0.1",
        units="mm",
        documents="part:bracket@1",
        critical_dimensions={
            "bore_dia": CriticalDimension(
                param="bore_1.diameter",
                tolerance={"type": "fit", "value": "H7"},
            )
        },
    )
    scheme = resolve_scheme_from_snapshot(snapshot, intent)
    assert isinstance(scheme, ResolvedScheme)
    assert scheme.drawing_intent == "drawing_intent:BRK-001-DI"
    assert len(scheme.entries) == EXPECTED_ENTRIES_COUNT

    # Check that bore_1.diameter has tolerance linked to critical
    bore_entries = [e for e in scheme.entries.values() if "bore_1.diameter" in e.covers]
    assert len(bore_entries) == 1
    assert bore_entries[0].tolerance == {"critical": "bore_dia"}
    assert bore_entries[0].status == "shown"


def test_apply_cleanup_to_scheme() -> None:
    snapshot = _make_sample_snapshot(duplicate=False)
    intent = DrawingIntent(
        id="BRK-001-DI",
        schema_version="0.1",
        units="mm",
        documents="part:bracket@1",
    )
    scheme = resolve_scheme_from_snapshot(snapshot, intent)
    # Simulate a plan directing to hide bore_1.diameter
    plan = DuplicatePlan(
        to_keep=("bracket.width",),
        to_hide=(HideAction(annotation_key="a1", native_id="bore_1.diameter", reason="duplicate"),),
    )
    updated_scheme = apply_cleanup_to_scheme(scheme, plan)

    # One entry should be marked hidden with reason duplicate
    hidden_entries = [e for e in updated_scheme.entries.values() if e.status == "hidden"]
    assert len(hidden_entries) == 1
    assert hidden_entries[0].reason == "duplicate"
    assert "bore_1.diameter" in hidden_entries[0].covers


def test_scheme_overrides_applied() -> None:
    snapshot = _make_sample_snapshot(duplicate=False)
    intent = DrawingIntent(
        id="BRK-001-DI",
        schema_version="0.1",
        units="mm",
        documents="part:bracket@1",
        scheme_overrides={
            "ds_custom_note": {
                "kind": "note",
                "source": "authored",
                "status": "shown",
                "reason": "drawing requirement",
            }
        },
    )
    scheme = resolve_scheme_from_snapshot(snapshot, intent)
    assert "ds_custom_note" in scheme.entries
    entry = scheme.entries["ds_custom_note"]
    assert entry.origin == "authored"
    assert entry.source == "authored"
    assert entry.status == "shown"
