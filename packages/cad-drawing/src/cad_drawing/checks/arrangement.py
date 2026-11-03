"""Shared extension lines of chain and baseline arrangements (spec 11.5.2, D1)."""

from collections.abc import Iterable, Mapping, Sequence

from cad_drawing.checks.geometry2d import Vec, point_segment_distance
from cad_drawing.checks.measure import Contact
from cad_drawing.checks.primitives import Prim

type OwnExtensions = Mapping[tuple[str, str], Sequence[Prim]]


def own_extensions(prims: Iterable[Prim]) -> OwnExtensions:
    """Extension lines keyed by (annotation, attachment entity)."""
    found: dict[tuple[str, str], list[Prim]] = {}
    for p in prims:
        if p.kind == "extension_line" and p.entity is not None:
            found.setdefault((p.owner, p.entity), []).append(p)
    return found


def distance_to(point: Vec, p: Prim) -> float:
    return min((point_segment_distance(point, s) for s in p.segments), default=float("inf"))


def _within(inner: Prim, outer: Prim, eps: float) -> bool:
    """Both end points of ``inner`` lie within ``eps`` of ``outer``."""
    if not inner.segments:
        return False
    ends = (inner.segments[0].a, inner.segments[-1].b)
    return all(distance_to(pt, outer) <= eps for pt in ends)


def coincident(a: Prim, b: Prim, eps: float) -> bool:
    """Extension lines of one attachment entity, one lying along the other within ``eps``."""
    return (
        a.entity is not None and a.entity == b.entity and (_within(a, b, eps) or _within(b, a, eps))
    )


def shared_extension(line: Prim, own: OwnExtensions, eps: float) -> bool:
    """The extension line ``line`` is shared with another annotation on the same entity."""
    if line.entity is None:
        return False
    return any(
        owner != line.owner and entity == line.entity and any(coincident(line, m, eps) for m in ms)
        for (owner, entity), ms in own.items()
    )


def _on_stretch(contact: Contact, first: Prim, second: Prim, eps: float) -> bool:
    """Both points of the contact lie within ``eps`` of both lines (their common stretch)."""
    return all(distance_to(point, line) <= eps for point in contact for line in (first, second))


def shared_pairs(
    owner_a: str, owner_b: str, own: OwnExtensions, eps: float
) -> list[tuple[Prim, Prim]]:
    """Coincident extension lines of two annotations on a common entity."""
    pairs: list[tuple[Prim, Prim]] = []
    for (owner, entity), mine in own.items():
        if owner != owner_a:
            continue
        pairs.extend(
            (ea, eb)
            for ea in mine
            for eb in own.get((owner_b, entity), ())
            if coincident(ea, eb, eps)
        )
    return pairs


def in_arrangement(a: Prim, b: Prim, contact: Contact, own: OwnExtensions, eps: float) -> bool:
    """The contact of ``a`` and ``b`` belongs to a chain or baseline arrangement.

    Two dimension lines or arrowheads: both points lie within ``eps`` of a pair of coincident
    extension lines, inside the stretch where the two overlap. A dimension line and an extension
    line: both points lie within ``eps`` of that extension line and of the dimension's own
    coincident extension line.
    """
    if a.kind != "extension_line" and b.kind != "extension_line":
        return any(
            _on_stretch(contact, ea, eb, eps) for ea, eb in shared_pairs(a.owner, b.owner, own, eps)
        )
    ext, other = (a, b) if a.kind == "extension_line" else (b, a)
    if ext.entity is None:
        return False
    return any(
        coincident(mine, ext, eps) and _on_stretch(contact, mine, ext, eps)
        for mine in own.get((other.owner, ext.entity), ())
    )
