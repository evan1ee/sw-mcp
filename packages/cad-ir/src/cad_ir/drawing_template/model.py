"""Dataclass models for Drawing Template IR (spec 11.12)."""

from dataclasses import dataclass
from typing import Final

PAPER_SIZES_MM: Final[dict[str, tuple[float, float]]] = {
    "A4": (210.0, 297.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned 2D rectangle in sheet millimetres."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


@dataclass(frozen=True, slots=True)
class Margins:
    """Sheet border margins in millimetres."""

    left: float
    right: float
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class TitleBlockLine:
    """A line segment within a title block zone."""

    key: str
    start: tuple[float, float]
    end: tuple[float, float]
    line_width: float | None = None


@dataclass(frozen=True, slots=True)
class StaticText:
    """Static text placed on the sheet."""

    key: str
    text: str
    box: Rect
    height: float
    align: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateField:
    """An attribute link field in the title block."""

    key: str
    source: tuple[str, ...]
    required: bool
    label: str | None
    box: Rect
    height: float
    align: str | None = None


@dataclass(frozen=True, slots=True)
class DrawingTemplate:
    """An authored drawing template / sheet format specification."""

    id: str | None
    schema_version: str
    display_name: str | None
    paper_size: str
    orientation: str
    margins: Margins
    border_line_width: float | None
    zones: tuple[tuple[str, Rect], ...]
    lines: tuple[tuple[str, TitleBlockLine], ...]
    texts: tuple[tuple[str, StaticText], ...]
    fields: tuple[tuple[str, TemplateField], ...]
    revision_table_box: Rect | None

    @property
    def sheet_size_mm(self) -> tuple[float, float]:
        raw_w, raw_h = PAPER_SIZES_MM.get(self.paper_size, (0.0, 0.0))
        min_dim = min(raw_w, raw_h)
        max_dim = max(raw_w, raw_h)
        if self.orientation == "portrait":
            return (min_dim, max_dim)
        return (max_dim, min_dim)

    @property
    def border_rect(self) -> Rect:
        sheet_w, sheet_h = self.sheet_size_mm
        return Rect(
            min_x=self.margins.left,
            min_y=self.margins.bottom,
            max_x=sheet_w - self.margins.right,
            max_y=sheet_h - self.margins.top,
        )
