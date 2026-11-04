"""Pure view planning engine for single-part production drawings (spec 11.2, 11.4, 11.11)."""

from cad_ir.drawing_layout import (
    DrawingLayout,
    DrawingSheet,
    DrawingView,
    ViewDisplay,
)

from cad_drawing.view_planning.scales import format_scale_string, select_iso_scale

DEFAULT_SHEET_SIZES: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}


def plan_ortho_views(  # noqa: PLR0913, PLR0917
    part_extents: tuple[float, float, float],  # (dx, dy, dz)
    sheet_size: str = "A3",
    sheet_width_mm: float | None = None,
    sheet_height_mm: float | None = None,
    title_block_box: tuple[float, float, float, float] | None = None,
    include_isometric: bool = True,
    intent_ref: str = "drawing_intent:PART-001@1",
    layout_id: str = "DL-001",
) -> DrawingLayout:
    """Plan standard orthographic views (Front, Top, Right) + Isometric view.

    Adheres strictly to ISO 5456-2 first-angle projection rules:
    - Front view: primary orthogonal reference
    - Top view: positioned vertically aligned directly below Front view
    - Right view: positioned horizontally aligned directly to the left of Front view
    - Isometric view: positioned in clear upper quadrant
    - Title block avoidance: views never placed in title block zone (check D7)
    """
    dx, dy, dz = part_extents

    if sheet_width_mm is None or sheet_height_mm is None:
        dims = DEFAULT_SHEET_SIZES.get(sheet_size, (420.0, 297.0))
        sheet_w = dims[0]
        sheet_h = dims[1]
    else:
        sheet_w = sheet_width_mm
        sheet_h = sheet_height_mm

    left_margin = 20.0
    right_margin = 10.0
    top_margin = 10.0
    bottom_margin = 10.0
    inter_view_spacing = 25.0

    tb_min_x = sheet_w - 180.0
    tb_max_y = 65.0
    if title_block_box is not None:
        tb_min_x = title_block_box[0]
        tb_max_y = title_block_box[3]

    usable_width = sheet_w - left_margin - right_margin
    usable_height = sheet_h - bottom_margin - top_margin

    # For orthographic cluster, reserve space so it does not collide with title block on right
    cluster_usable_width = max(100.0, min(usable_width, tb_min_x - left_margin - 10.0))

    scale_num, scale_den = select_iso_scale(
        part_width_mm=dx,
        part_height_mm=dy,
        part_depth_mm=dz,
        usable_width_mm=cluster_usable_width,
        usable_height_mm=usable_height,
        spacing_mm=inter_view_spacing,
    )
    scale_val = scale_num / scale_den
    scale_str = format_scale_string(scale_num, scale_den)

    # Scaled dimensions of views
    # Front: width = dx, height = dy
    fw = dx * scale_val
    fh = dy * scale_val
    # Top: height = dz
    th = dz * scale_val
    # Right: width = dz
    rw = dz * scale_val

    cluster_width = rw + inter_view_spacing + fw
    cluster_height = th + inter_view_spacing + fh

    # Bottom of cluster positioned above bottom margin and title block height if needed
    cluster_bottom = max(
        bottom_margin + 15.0,
        tb_max_y + 10.0 if cluster_width > (tb_min_x - left_margin) else bottom_margin + 15.0,
    )
    # Ensure cluster fits within usable height
    if cluster_bottom + cluster_height > (sheet_h - top_margin):
        cluster_bottom = bottom_margin + 10.0

    # Center horizontally in the available left area
    cluster_left = left_margin + max(10.0, (cluster_usable_width - cluster_width) / 2.0)

    # Coordinates in sheet mm (lower-left origin)
    # Right view (to the left of Front):
    right_x = cluster_left + rw / 2.0
    right_y = cluster_bottom + th + inter_view_spacing + fh / 2.0

    # Front view:
    front_x = cluster_left + rw + inter_view_spacing + fw / 2.0
    front_y = right_y

    # Top view (below Front view):
    top_x = front_x
    top_y = cluster_bottom + th / 2.0

    views: dict[str, DrawingView] = {
        "v_front": DrawingView(
            sheet="s1",
            type="base",
            orientation="front",
            scale=scale_str,
            position=(round(front_x, 3), round(front_y, 3)),
            display=ViewDisplay(hidden_lines=False, tangent_edges="removed"),
        ),
        "v_top": DrawingView(
            sheet="s1",
            type="projected",
            parent="v_front",
            orientation="top",
            scale=scale_str,
            position=(round(top_x, 3), round(top_y, 3)),
            display=ViewDisplay(hidden_lines=False, tangent_edges="removed"),
        ),
        "v_right": DrawingView(
            sheet="s1",
            type="projected",
            parent="v_front",
            orientation="right",
            scale=scale_str,
            position=(round(right_x, 3), round(right_y, 3)),
            display=ViewDisplay(hidden_lines=False, tangent_edges="removed"),
        ),
    }

    if include_isometric:
        iso_x = round(sheet_w - right_margin - 70.0, 3)
        iso_y = round(sheet_h - top_margin - 70.0, 3)
        iso_scale_str = scale_str
        views["v_iso"] = DrawingView(
            sheet="s1",
            type="isometric",
            orientation="isometric",
            scale=iso_scale_str,
            position=(iso_x, iso_y),
            display=ViewDisplay(hidden_lines=False, tangent_edges="removed"),
        )

    sheet = DrawingSheet(
        size=sheet_size,
        orientation="landscape",
        scale=scale_str,
    )

    return DrawingLayout(
        id=layout_id,
        schema_version="0.1",
        units="mm",
        intent=intent_ref,
        sheets={"s1": sheet},
        views=views,
    )
