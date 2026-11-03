"""Builders for in-code sheets, shared through the ``b`` fixture (importlib mode has no imports)."""

import math
from collections.abc import Sequence

import pytest
from cad_drawing.checks.geometry2d import Vec
from cad_drawing.checks.snapshot import (
    Annotation,
    AnnotationKind,
    ArcCurve,
    Arrowhead,
    Curve,
    Edge,
    EdgeKind,
    ExtensionLine,
    PolylineCurve,
    Rect,
    Sheet,
    TextBox,
    TextMethod,
    View,
)

BORDER = Rect((10.0, 5.0), (292.0, 205.0))


class Builder:
    """Small constructors for snapshot dataclasses; every argument has a sensible default."""

    @staticmethod
    def line(*points: Vec) -> PolylineCurve:
        return PolylineCurve(tuple(points))

    @staticmethod
    def arc(center: Vec, radius: float, start_deg: float, end_deg: float) -> ArcCurve:
        return ArcCurve(center, radius, start_deg, end_deg)

    @staticmethod
    def ext(entity: str, *points: Vec) -> ExtensionLine:
        return ExtensionLine(tuple(points), entity)

    @staticmethod
    def box(  # noqa: PLR0913
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        method: TextMethod = "display_data",
        height: float = 2.0,
    ) -> TextBox:
        return TextBox(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), height, method, "x")

    @staticmethod
    def rotated_box(  # noqa: PLR0913
        cx: float, cy: float, w: float, h: float, deg: float, *, method: TextMethod = "display_data"
    ) -> TextBox:
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        corners = [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]
        return TextBox((corners[0], corners[1], corners[2], corners[3]), h, method, "x")

    @staticmethod
    def annotation(  # noqa: PLR0913
        key: str,
        *,
        kind: AnnotationKind = "dimension",
        dimension_lines: Sequence[Curve] = (),
        extension_lines: Sequence[ExtensionLine] = (),
        arrowheads: Sequence[Sequence[Vec]] = (),
        leaders: Sequence[Sequence[Vec]] = (),
        text_boxes: Sequence[TextBox] = (),
    ) -> Annotation:
        return Annotation(
            key=key,
            kind=kind,
            native_id=key,
            tag=None,
            view=None,
            attachments=(),
            dimension_lines=tuple(dimension_lines),
            extension_lines=tuple(extension_lines),
            arrowheads=tuple(Arrowhead(tuple(a)) for a in arrowheads),
            leaders=tuple(tuple(x) for x in leaders),
            text_boxes=tuple(text_boxes),
        )

    @staticmethod
    def view(
        key: str, edges: Sequence[tuple[Curve, EdgeKind]] = (), outline: Rect | None = None
    ) -> View:
        return View(
            key=key,
            native_id=key,
            scale=1.0,
            outline=outline or Rect((50.0, 50.0), (100.0, 100.0)),
            edges=tuple(Edge(c, k) for c, k in edges),
        )

    @staticmethod
    def sheet(  # noqa: PLR0913
        annotations: Sequence[Annotation] = (),
        views: Sequence[View] = (),
        *,
        border: Rect = BORDER,
        title_block: Sequence[Rect] = (),
        key: str = "s_0",
        index: int = 0,
    ) -> Sheet:
        return Sheet(
            key=key,
            index=index,
            native_id="Sheet1",
            size_mm=(297.0, 210.0),
            border=border,
            title_block=tuple(title_block),
            views=tuple(views),
            annotations=tuple(annotations),
        )


@pytest.fixture
def b() -> Builder:
    return Builder()
