"""Drawing annotation insertion, center mark placement, and duplicate cleanup pipeline.

Spec 11.4, 11.10, 11.10.1, 6.5.2.
Coordinates annotation insertion, auto-arrange, ISO 128 center marks, and duplicate
dimension cleanup using pure dimension scheme resolution.
"""

from typing import cast

from cad_drawing.checks.snapshot import Snapshot, parse_snapshot
from cad_drawing.dimension_scheme.cleanup import (
    apply_cleanup_to_scheme,
    plan_duplicate_cleanup,
)
from cad_drawing.dimension_scheme.resolver import resolve_scheme_from_snapshot
from cad_ir.core import IssueReport
from cad_ir.core.json_types import JsonValue
from cad_ir.drawing_intent import DrawingIntent
from cad_ir.drawing_layout.model import DrawingLayout
from cad_ir.generated.ipc import Operation
from cad_ir.resolved_scheme import ResolvedScheme

_DEFAULT_ARRANGE_SPACING_MM = 10.0


def _is_isometric(view_type: str, orientation: str | None) -> bool:
    if view_type.lower() == "isometric":
        return True
    return bool(orientation and orientation.lower() == "isometric")


def plan_annotation_insertion_ops(
    layout: DrawingLayout,
    intent: DrawingIntent | None = None,
    job_prefix: str = "ann",
    view_names: dict[str, str] | None = None,
    spacing_mm: float = _DEFAULT_ARRANGE_SPACING_MM,
) -> list[Operation]:
    """Generates IPC operations to insert model items, center marks, and auto-arrange dimensions.

    Spec 11.4, 6.5.2:
    1. model_items.insert: imports dimensions and callouts across model with duplicates enabled.
    2. center_mark.add: adds ISO 128 center marks to orthographic views.
    3. dimensions.auto_arrange: aligns dimensions in each orthographic view with uniform spacing.
    """
    ops: list[Operation] = []

    # 1. model_items.insert
    model_items_params: dict[str, JsonValue] = {
        "source": "entire_model",
        "duplicate_dims": True,
        "hidden_feature_dims": False,
        "use_placement_in_sketch": False,
        "marked_for_drawing": True,
        "not_marked_for_drawing": True,
        "hole_callouts": True,
    }
    ops.append(
        Operation(
            operation_id=f"{job_prefix}:model_items:0",
            op="model_items.insert",
            params=model_items_params,
        )
    )

    # Filter orthographic views
    ortho_views: list[tuple[str, str]] = []
    for view_id, view in layout.views.items():
        if _is_isometric(view.type, view.orientation):
            continue
        vname = view_names.get(view_id, view_id) if view_names else view_id
        ortho_views.append((view_id, vname))

    # 2. center_mark.add for orthographic views
    for idx, (_, vname) in enumerate(ortho_views):
        cm_params: dict[str, JsonValue] = {
            "view": vname,
            "hole_centers": True,
            "slot_centers": True,
            "use_doc_defaults": True,
        }
        ops.append(
            Operation(
                operation_id=f"{job_prefix}:center_mark:{idx}",
                op="center_mark.add",
                params=cm_params,
            )
        )

    # 3. dimensions.auto_arrange for orthographic views
    for idx, (_, vname) in enumerate(ortho_views):
        aa_params: dict[str, JsonValue] = {
            "view": vname,
            "spacing_mm": spacing_mm,
        }
        ops.append(
            Operation(
                operation_id=f"{job_prefix}:auto_arrange:{idx}",
                op="dimensions.auto_arrange",
                params=aa_params,
            )
        )

    return ops


def plan_dimension_cleanup_ops(
    snapshot: Snapshot | dict[str, JsonValue],
    intent: DrawingIntent | None = None,
    job_prefix: str = "cleanup",
) -> tuple[list[Operation], ResolvedScheme]:
    """Analyzes drawing snapshot, identifies duplicate dimensions, and plans dimension.hide ops.

    Spec 11.4, 11.10.1:
    - Derives ResolvedScheme from snapshot dimensions.
    - Groups dimensions by model parameter across views.
    - Retains primary view dimension and generates dimension.hide ops for redundant copies.
    - Updates ResolvedScheme entries to status='hidden' with reason='duplicate'.
    """
    snap: Snapshot
    if isinstance(snapshot, dict):
        res = parse_snapshot(cast(JsonValue, snapshot))
        if isinstance(res, IssueReport):
            err_msg = "; ".join(f"{i.pointer}: {i.message}" for i in res.issues)
            raise ValueError(f"Invalid snapshot passed to cleanup planner: {err_msg}")
        snap = res
    else:
        snap = snapshot

    plan = plan_duplicate_cleanup(snap)
    base_scheme = resolve_scheme_from_snapshot(snap, intent)
    resolved_scheme = apply_cleanup_to_scheme(base_scheme, plan)

    ops: list[Operation] = []
    for idx, hide_action in enumerate(plan.to_hide):
        hide_params: dict[str, JsonValue] = {
            "annotation": hide_action.native_id,
            "reason": hide_action.reason,
        }
        ops.append(
            Operation(
                operation_id=f"{job_prefix}:hide:{idx}",
                op="dimension.hide",
                params=hide_params,
            )
        )

    return ops, resolved_scheme
