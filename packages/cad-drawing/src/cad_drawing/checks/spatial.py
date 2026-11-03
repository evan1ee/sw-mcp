"""Uniform-grid candidate pairs that keep pair tests near-linear."""

import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from cad_drawing.checks.geometry2d import aabb
from cad_drawing.checks.primitives import Prim

type Box = tuple[float, float, float, float]
type Cell = tuple[int, int]


def _prim_boxes(p: Prim) -> tuple[Box, ...]:
    """Per-segment boxes, plus the whole box of the polygon (its interior can contain others)."""
    boxes = [aabb((s.a, s.b)) for s in p.segments]
    if p.polygon:
        boxes.append(aabb(p.polygon))
    return tuple(boxes)


def _cells(box: Box, pad: float, cell: float) -> Iterator[Cell]:
    x0, y0 = math.floor((box[0] - pad) / cell), math.floor((box[1] - pad) / cell)
    x1, y1 = math.floor((box[2] + pad) / cell), math.floor((box[3] + pad) / cell)
    for i in range(x0, x1 + 1):
        for j in range(y0, y1 + 1):
            yield (i, j)


def _overall(boxes: Sequence[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _meet(a: Box, b: Box, pad: float) -> bool:
    return a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]


type Select = Callable[[Prim], bool]


@dataclass(frozen=True, slots=True)
class GridIndex:
    """Cells map to the list positions of the prims whose geometry touches them."""

    cell_mm: float
    prims: tuple[Prim, ...]
    boxes: tuple[Box | None, ...]
    cells: Mapping[Cell, tuple[int, ...]]

    @staticmethod
    def build(prims: Sequence[Prim], cell_mm: float = 10.0) -> "GridIndex":
        per_prim = [_prim_boxes(p) for p in prims]
        grid: dict[Cell, list[int]] = {}
        for pos, boxes in enumerate(per_prim):
            seen: set[Cell] = set()
            for box in boxes:
                for c in _cells(box, 0.0, cell_mm):
                    if c not in seen:
                        seen.add(c)
                        grid.setdefault(c, []).append(pos)
        return GridIndex(
            cell_mm,
            tuple(prims),
            tuple(_overall(b) if b else None for b in per_prim),
            MappingProxyType({c: tuple(v) for c, v in grid.items()}),
        )

    def candidate_pairs(
        self, left: Select, right: Select | None, pad: float
    ) -> Iterator[tuple[Prim, Prim]]:
        """Each unordered pair (``left`` prim, ``right`` prim), or two ``left`` prims when
        ``right`` is None, whose boxes, padded, meet. A pair is yielded once.

        Order follows the index order of the first element, then of the second.
        """
        other_side = left if right is None else right
        allowed = {pos for pos, p in enumerate(self.prims) if other_side(p)}
        emitted: set[tuple[int, int]] = set()
        for pos, p in enumerate(self.prims):
            box = self.boxes[pos]
            if box is None or not left(p):
                continue
            hits: set[int] = set()
            for sub in _prim_boxes(p):
                for c in _cells(sub, pad, self.cell_mm):
                    hits.update(self.cells.get(c, ()))
            for other in sorted(hits & allowed):
                key = (min(pos, other), max(pos, other))
                other_box = self.boxes[other]
                if other == pos or key in emitted or other_box is None:
                    continue
                if not _meet(box, other_box, pad):
                    continue
                emitted.add(key)
                yield (p, self.prims[other])
