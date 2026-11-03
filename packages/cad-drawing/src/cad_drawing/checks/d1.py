"""D1: crossing dimensions (spec 11.5.2)."""

from collections.abc import Sequence

from cad_drawing.checks.arrangement import in_arrangement, own_extensions
from cad_drawing.checks.failures import (
    Candidate,
    CheckFailure,
    CheckItem,
    emit_failures,
    keep_min,
)
from cad_drawing.checks.measure import Measurement, contact_distance, contacts
from cad_drawing.checks.primitives import Prim
from cad_drawing.checks.snapshot import Sheet
from cad_drawing.checks.spatial import GridIndex
from cad_drawing.checks.thresholds import CheckThresholds

_D1_KINDS = {"dimension_line", "arrowhead", "extension_line"}


def check_d1(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> tuple[CheckFailure, ...]:
    """Dimension/extension primitives of different dimensions within epsilon of each other.

    One failure per annotation pair and class (line x line, line x extension line), at the
    closest contact that is not part of a chain or baseline arrangement.
    """
    eps = t.epsilon_mm
    cand = [p for p in prims if p.kind in _D1_KINDS]
    own = own_extensions(cand)
    best: dict[tuple[str, ...], Candidate] = {}
    for a, b in GridIndex.build(cand).candidate_pairs(lambda _: True, None, eps):
        if a.owner == b.owner or (a.kind == "extension_line" and b.kind == "extension_line"):
            continue
        loose = [c for c in contacts(a, b, eps) if not in_arrangement(a, b, c, own, eps)]
        if not loose:
            continue
        nearest = min(loose, key=contact_distance)
        m = Measurement(contact_distance(nearest), nearest[0], nearest[1])
        owners = tuple(sorted((a.owner, b.owner)))
        klass = "ext" if "extension_line" in (a.kind, b.kind) else "line"
        entries = (
            (CheckItem("annotation", a.owner), None),
            (CheckItem("annotation", b.owner), None),
        )
        keep_min(best, (*owners, klass), (m, entries, eps))
    return emit_failures("D1", sheet.key, best)
