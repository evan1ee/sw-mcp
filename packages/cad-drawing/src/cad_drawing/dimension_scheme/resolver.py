"""Pure dimension scheme resolution from drawing geometry snapshot (spec 11.4, 11.10.1)."""

from typing import Any

from cad_ir.core.derived_ids import scheme_entry_id
from cad_ir.drawing_intent import DrawingIntent
from cad_ir.resolved_scheme import ResolvedScheme, SchemeEntry

from cad_drawing.checks.snapshot import Annotation, Snapshot


def _infer_kind(ann: Annotation) -> str:
    """Infer dimension kind from text or geometry."""
    for tb in ann.text_boxes:
        txt = tb.text
        if "Ø" in txt or "dia" in txt.lower():
            return "diameter"
        if txt.startswith("R") or "rad" in txt.lower():
            return "radius"
        if "°" in txt or "deg" in txt.lower():
            return "angular"
    return "linear"


def _match_tolerance(covers: tuple[str, ...], intent: DrawingIntent | None) -> Any:
    if intent is not None and intent.critical_dimensions:
        for crit_id, crit_dim in intent.critical_dimensions.items():
            if crit_dim.param and crit_dim.param in covers:
                return {"critical": crit_id}
    return "general"


def _apply_overrides(entries: dict[str, SchemeEntry], intent: DrawingIntent) -> None:
    if not intent.scheme_overrides:
        return
    for override_id, override_dict in intent.scheme_overrides.items():
        if override_id in entries:
            existing = entries[override_id]
            entries[override_id] = SchemeEntry(
                kind=str(override_dict.get("kind", existing.kind)),
                source=str(override_dict.get("source", existing.source)),
                status=str(override_dict.get("status", existing.status)),
                origin="authored",
                covers=tuple(override_dict.get("covers", existing.covers)),
                measures=override_dict.get("measures", existing.measures),
                tolerance=override_dict.get("tolerance", existing.tolerance),
                reason=override_dict.get("reason", existing.reason),
                auxiliary=bool(override_dict.get("auxiliary", existing.auxiliary)),
            )
        else:
            entries[override_id] = SchemeEntry(
                kind=str(override_dict.get("kind", "linear")),
                source=str(override_dict.get("source", "authored")),
                status=str(override_dict.get("status", "shown")),
                origin="authored",
                covers=tuple(override_dict.get("covers", ())),
                measures=override_dict.get("measures"),
                tolerance=override_dict.get("tolerance", "general"),
                reason=override_dict.get("reason"),
                auxiliary=bool(override_dict.get("auxiliary", False)),
            )


def resolve_scheme_from_snapshot(
    snapshot: Snapshot, intent: DrawingIntent | None = None
) -> ResolvedScheme:
    """Extract inserted dimensions from a drawing snapshot and resolve into a ResolvedScheme.

    Derives stable entry IDs from kind, covers, measures, and source per Spec 3.4.4.
    Matches critical dimensions from DrawingIntent and applies scheme_overrides (Spec 11.10.1).
    """
    entries: dict[str, SchemeEntry] = {}

    for sheet in snapshot.sheets:
        for ann in sheet.annotations:
            if ann.kind != "dimension":
                continue
            covers = tuple(sorted(set(ann.parameters or (ann.native_id,))))
            kind = _infer_kind(ann)
            source = "model_item"
            eid = scheme_entry_id(kind, covers, None, source)

            if eid not in entries:
                tol = _match_tolerance(covers, intent)
                entries[eid] = SchemeEntry(
                    kind=kind,
                    source=source,
                    status="shown",
                    origin="derived",
                    covers=covers,
                    measures=None,
                    tolerance=tol,
                    reason=None,
                    auxiliary=False,
                )

    if intent is not None:
        _apply_overrides(entries, intent)

    intent_ref = f"drawing_intent:{intent.id}" if intent is not None else "drawing_intent:default"
    part_rev = intent.revision if intent is not None else 1

    return ResolvedScheme(
        schema_version="0.1",
        drawing_intent=intent_ref,
        entries=entries,
        part_revision=part_rev,
        pipeline_version="1.0",
    )
