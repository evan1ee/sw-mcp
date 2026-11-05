"""Duplicate dimension identification and cleanup engine (spec 11.4, 11.10.1)."""

from dataclasses import dataclass

from cad_ir.resolved_scheme import ResolvedScheme, SchemeEntry

from cad_drawing.checks.snapshot import Annotation, Snapshot


@dataclass(frozen=True, slots=True)
class HideAction:
    """Action to hide a redundant or duplicate dimension annotation."""

    annotation_key: str
    native_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class DuplicatePlan:
    """Outcome of duplicate dimension analysis across views."""

    to_keep: tuple[str, ...]  # native_ids kept
    to_hide: tuple[HideAction, ...]  # annotations to hide


def plan_duplicate_cleanup(snapshot: Snapshot) -> DuplicatePlan:
    """Identify duplicate parameter dimensions across drawing views.

    For parameters appearing in multiple views, selects a primary view (preferring front/base)
    and schedules all redundant copies for hiding with reason 'duplicate' (Spec 11.4).
    """
    annotations: list[Annotation] = []
    for sheet in snapshot.sheets:
        for ann in sheet.annotations:
            if ann.kind == "dimension":
                annotations.append(ann)

    # Group annotations by parameter
    param_to_anns: dict[str, list[Annotation]] = {}
    for ann in annotations:
        for p in ann.parameters or ():
            param_to_anns.setdefault(p, []).append(ann)

    to_hide: list[HideAction] = []
    to_keep: set[str] = set()

    for p in sorted(param_to_anns):
        candidates = param_to_anns[p]
        if len(candidates) <= 1:
            if candidates:
                to_keep.add(candidates[0].native_id)
            continue

        # Sort candidates: prefer front/base views, then deterministic by native_id
        def _view_priority(a: Annotation) -> tuple[int, str]:
            view = (a.view or "").lower()
            if "front" in view or "base" in view:
                return (0, a.native_id)
            if "top" in view:
                return (1, a.native_id)
            if "right" in view or "side" in view:
                return (2, a.native_id)
            return (3, a.native_id)

        sorted_candidates = sorted(candidates, key=_view_priority)
        primary = sorted_candidates[0]
        to_keep.add(primary.native_id)

        for dup in sorted_candidates[1:]:
            to_hide.append(
                HideAction(
                    annotation_key=dup.key,
                    native_id=dup.native_id,
                    reason="duplicate",
                )
            )

    return DuplicatePlan(
        to_keep=tuple(sorted(to_keep)),
        to_hide=tuple(to_hide),
    )


def apply_cleanup_to_scheme(scheme: ResolvedScheme, plan: DuplicatePlan) -> ResolvedScheme:
    """Apply cleanup decisions to a ResolvedScheme, setting status='hidden' on duplicates."""
    hidden_ids = {h.native_id for h in plan.to_hide}
    new_entries: dict[str, SchemeEntry] = {}

    for entry_id, entry in scheme.entries.items():
        # Check if entry is affected by hide actions
        should_hide = False
        reason = entry.reason
        if any(cov in hidden_ids for cov in entry.covers) or entry_id in hidden_ids:
            should_hide = True
            reason = "duplicate"

        if should_hide:
            new_entries[entry_id] = SchemeEntry(
                kind=entry.kind,
                source=entry.source,
                status="hidden",
                origin=entry.origin,
                covers=entry.covers,
                measures=entry.measures,
                tolerance=entry.tolerance,
                reason=reason or "duplicate",
                auxiliary=entry.auxiliary,
            )
        else:
            new_entries[entry_id] = entry

    return ResolvedScheme(
        schema_version=scheme.schema_version,
        drawing_intent=scheme.drawing_intent,
        entries=new_entries,
        part_revision=scheme.part_revision,
        pipeline_version=scheme.pipeline_version,
    )
