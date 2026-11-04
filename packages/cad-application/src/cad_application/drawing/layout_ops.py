"""Drawing layout to IPC operations mapping and as-built derivation.

Spec 11.4, 11.11, 6.5.2.
Transforms planned DrawingLayout into view.create backend operations and derives
as-built layouts from drawing snapshot geometry.
"""

from cad_drawing.view_planning.scales import parse_scale_string
from cad_ir.core.json_types import JsonValue
from cad_ir.drawing_layout.model import (
    DrawingLayout,
    DrawingView,
)
from cad_ir.generated.ipc import Operation

_MIN_COORDS_COUNT = 2


def layout_to_create_ops(
    layout: DrawingLayout,
    model_path: str,
    job_prefix: str,
    sheet_name: str | None = None,
) -> list[Operation]:
    """Converts a planned DrawingLayout into an ordered list of view.create operations."""
    ops: list[Operation] = []

    for idx, (view_id, view) in enumerate(layout.views.items()):
        num, den = parse_scale_string(view.scale)
        scale_val = num / den
        display_mode = "hlv" if (view.display and view.display.hidden_lines) else "hlr"
        tangent_edges = view.display.tangent_edges if view.display else "removed"
        target_sheet = sheet_name or view.sheet

        params: dict[str, JsonValue] = {
            "model_path": model_path,
            "sheet": target_sheet,
            "view_type": view.type,
            "orientation": view.orientation,
            "position": [round(view.position[0], 3), round(view.position[1], 3)],
            "scale": scale_val,
            "view_name": view_id,
            "display_mode": display_mode,
            "tangent_edges": tangent_edges,
        }

        if view.parent:
            params["parent_view"] = view.parent
        if view.configuration and view.configuration != "Default":
            params["configuration"] = view.configuration

        op = Operation(
            operation_id=f"{job_prefix}:{idx}",
            op="view.create",
            params=params,
        )
        ops.append(op)

    return ops


def _extract_view_center(view_data: dict[str, JsonValue]) -> tuple[float, float] | None:
    outline_data = view_data.get("outline")
    if not isinstance(outline_data, dict):
        return None
    min_arr = outline_data.get("min")
    max_arr = outline_data.get("max")
    if (
        isinstance(min_arr, list)
        and len(min_arr) >= _MIN_COORDS_COUNT
        and isinstance(max_arr, list)
        and len(max_arr) >= _MIN_COORDS_COUNT
        and isinstance(min_arr[0], (int, float))
        and isinstance(min_arr[1], (int, float))
        and isinstance(max_arr[0], (int, float))
        and isinstance(max_arr[1], (int, float))
    ):
        cx = (float(min_arr[0]) + float(max_arr[0])) / 2.0
        cy = (float(min_arr[1]) + float(max_arr[1])) / 2.0
        return (round(cx, 3), round(cy, 3))
    return None


def _find_matching_view(
    pv: DrawingView,
    view_id: str,
    views_by_key: dict[str, dict[str, JsonValue]],
    all_snapshot_views: dict[str, JsonValue],
) -> dict[str, JsonValue] | None:
    match = views_by_key.get(view_id.lower())
    if match is not None:
        return match
    if not pv.orientation:
        return None
    for sv in all_snapshot_views.values():
        if isinstance(sv, dict):
            nid = str(sv.get("native_id", "")).lower()
            if pv.orientation.lower() in nid:
                return sv
    return None


def _resolve_snapshot_sheet(
    snapshot: dict[str, JsonValue],
    target_sheet_names: set[str],
) -> dict[str, JsonValue] | None:
    sheets_raw = snapshot.get("sheets")
    if not isinstance(sheets_raw, dict) or not sheets_raw:
        return None
    default_sheet: dict[str, JsonValue] | None = None
    for s_val in sheets_raw.values():
        if isinstance(s_val, dict):
            if default_sheet is None:
                default_sheet = s_val
            if s_val.get("native_id") in target_sheet_names:
                return s_val
    return default_sheet


def derive_as_built_layout(
    snapshot: dict[str, JsonValue],
    planned_layout: DrawingLayout,
) -> DrawingLayout:
    """Derives the as-built DrawingLayout from the read-back snapshot geometry."""
    sheet_dict = _resolve_snapshot_sheet(snapshot, set(planned_layout.sheets.keys()))
    if not sheet_dict:
        return planned_layout

    snapshot_views = sheet_dict.get("views")
    if not isinstance(snapshot_views, dict):
        return planned_layout

    views_by_key: dict[str, dict[str, JsonValue]] = {}
    for k, v in snapshot_views.items():
        if isinstance(v, dict):
            views_by_key[k.lower()] = v
            if "native_id" in v:
                views_by_key[str(v["native_id"]).lower()] = v

    new_views: dict[str, DrawingView] = {}
    for view_id, pv in planned_layout.views.items():
        match = _find_matching_view(pv, view_id, views_by_key, snapshot_views)
        new_pos = pv.position
        if match is not None:
            extracted_pos = _extract_view_center(match)
            if extracted_pos is not None:
                new_pos = extracted_pos

        new_views[view_id] = DrawingView(
            sheet=pv.sheet,
            type=pv.type,
            position=new_pos,
            scale=pv.scale,
            orientation=pv.orientation,
            configuration=pv.configuration,
            parent=pv.parent,
            display=pv.display,
            label=pv.label,
            modifiers=dict(pv.modifiers),
        )

    return DrawingLayout(
        id=planned_layout.id,
        schema_version=planned_layout.schema_version,
        units=planned_layout.units,
        intent=planned_layout.intent,
        sheets=planned_layout.sheets,
        views=new_views,
        annotations=planned_layout.annotations,
        revision=planned_layout.revision,
        part_path=planned_layout.part_path,
        drafting_standard=planned_layout.drafting_standard,
        template=planned_layout.template,
        tables=planned_layout.tables,
        title_block=planned_layout.title_block,
    )
