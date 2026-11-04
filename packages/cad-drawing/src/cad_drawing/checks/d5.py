"""D5: duplicate dimensions, the part that needs no Resolved Scheme (spec 11.5.3).

Auxiliary marking needs a Drawing Intent, so it is ``not_evaluated`` and D5 is never ``pass``
here. The duplicates part finds repeated model parameters and closed dimension chains.
"""

import math
from collections import deque
from collections.abc import Mapping, Sequence

from cad_drawing.checks.outcome import (
    CheckOutcome,
    CheckStatus,
    ReasonCode,
    RuleFailure,
    RuleItem,
    combine_status,
)
from cad_drawing.checks.snapshot import Annotation, PolylineCurve, Snapshot
from cad_drawing.checks.thresholds import CheckThresholds

type Adjacency = dict[str, list[tuple[str, str]]]
type GroupKey = tuple[str | None, int]
type Node = tuple[str, str]  # (sheet key, annotation key)


def _annotations(snapshot: Snapshot) -> list[tuple[str, Annotation]]:
    """Every annotation as ``(sheet key, annotation)``, in sheet then key order."""
    return [(s.key, a) for s in snapshot.sheets for a in sorted(s.annotations, key=lambda a: a.key)]


def _duplicate_failures(snapshot: Snapshot) -> list[RuleFailure]:
    owners: dict[str, list[Node]] = {}
    for sheet, annotation in _annotations(snapshot):
        for name in sorted(set(annotation.parameters or ())):
            owners.setdefault(name, []).append((sheet, annotation.key))
    failures: list[RuleFailure] = []
    for name in sorted(owners):
        nodes = owners[name]
        if len(nodes) < 2:  # noqa: PLR2004
            continue
        sheets = {sheet for sheet, _ in nodes}
        failures.append(
            RuleFailure(
                check="D5",
                sheet=next(iter(sheets)) if len(sheets) == 1 else None,
                code="duplicate_parameter",
                items=tuple(RuleItem("annotation", key, sheet) for sheet, key in nodes),
                detail=(("parameter", name),),
                message=f"parameter {name} is shown by {len(nodes)} annotations",
            )
        )
    return failures


def _direction_bin(annotation: Annotation, t: CheckThresholds) -> int | None:
    """Direction of the first non-zero segment, modulo 180 degrees, as a bin index."""
    lines = annotation.dimension_lines
    if not lines or not all(isinstance(c, PolylineCurve) for c in lines):
        return None
    first = lines[0]
    if not isinstance(first, PolylineCurve):
        return None
    for (x0, y0), (x1, y1) in zip(first.points, first.points[1:], strict=False):
        dx, dy = x1 - x0, y1 - y0
        if dx != 0.0 or dy != 0.0:
            bins = round(180.0 / t.parallel_deg)
            return round(math.degrees(math.atan2(dy, dx)) % 180.0 / t.parallel_deg) % bins
    return None


def _chain_entities(annotation: Annotation) -> tuple[str, str] | None:
    """The two different, non-empty entities of a candidate dimension."""
    if annotation.kind != "dimension" or annotation.parenthesized is not False:
        return None
    if len(annotation.extension_lines) != 2:  # noqa: PLR2004
        return None
    a, b = (e.entity for e in annotation.extension_lines)
    return (a, b) if a and b and a != b else None


def _path(adjacency: Adjacency, start: str, goal: str) -> list[str] | None:
    """Annotation keys on the path from ``start`` to ``goal``, or None when not connected."""
    came: dict[str, tuple[str, str] | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            keys: list[str] = []
            step = came[node]
            while step is not None:
                keys.append(step[1])
                step = came[step[0]]
            return keys
        for neighbour, key in adjacency.get(node, ()):
            if neighbour not in came:
                came[neighbour] = (node, key)
                queue.append(neighbour)
    return None


def _chain_failure(sheet: str, keys: Sequence[str]) -> RuleFailure:
    items = tuple(RuleItem("annotation", k, sheet) for k in sorted(keys))
    return RuleFailure(
        check="D5",
        sheet=sheet,
        code="closed_chain",
        items=items,
        detail=(),
        message=f"{len(items)} dimensions close a chain",
    )


def _chain_failures(snapshot: Snapshot, t: CheckThresholds) -> list[RuleFailure]:
    failures: list[RuleFailure] = []
    for sheet in snapshot.sheets:
        groups: dict[GroupKey, Adjacency] = {}
        for annotation in sorted(sheet.annotations, key=lambda a: a.key):
            entities = _chain_entities(annotation)
            bin_index = _direction_bin(annotation, t)
            if entities is None or bin_index is None:
                continue
            adjacency = groups.setdefault((annotation.view, bin_index), {})
            a, b = entities
            path = _path(adjacency, a, b)
            if path is not None:
                failures.append(_chain_failure(sheet.key, [annotation.key, *path]))
                continue
            adjacency.setdefault(a, []).append((b, annotation.key))
            adjacency.setdefault(b, []).append((a, annotation.key))
    return failures


def _data_missing(snapshot: Snapshot) -> bool:
    return any(
        a.kind == "dimension" and (a.parameters is None or a.parenthesized is None)
        for _, a in _annotations(snapshot)
    )


def check_d5(snapshot: Snapshot, t: CheckThresholds) -> CheckOutcome:
    index: Mapping[str, int] = {s.key: s.index for s in snapshot.sheets}
    failures = tuple(
        sorted(
            [*_duplicate_failures(snapshot), *_chain_failures(snapshot, t)],
            key=lambda f: f.sort_key(index),
        )
    )
    duplicates: CheckStatus = "pass"
    if failures:
        duplicates = "fail"
    elif _data_missing(snapshot):
        duplicates = "not_evaluated"
    reasons: list[ReasonCode] = ["drawing_intent_required"]
    if duplicates == "not_evaluated":
        reasons.append("dimension_data_missing")
    marking: CheckStatus = "not_evaluated"
    return CheckOutcome(
        status=combine_status((marking, duplicates)),
        failures=failures,
        reasons=tuple(reasons),
        parts=(("auxiliary_marking", marking), ("duplicates", duplicates)),
    )
