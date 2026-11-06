"""Score an agent's answer for a case: valid graph with the right facts, or a refusal."""

import math
from typing import Any

from cad_compiler.validator.semantic import validate_graph
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_verification.part import expected_geometry

from cad_application.authoring_eval.cases import CASES, Case, Facts

REL_TOL = 1e-3
ABS_TOL = 1e-6

Answer = dict[str, Any] | None  # None means the agent refused


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def _all_close(actual: tuple[float, ...], expected: tuple[float, ...]) -> bool:
    return len(actual) == len(expected) and all(
        _close(a, b) for a, b in zip(actual, expected, strict=True)
    )


def _compare(facts: Facts, graph: PartGraph) -> list[str]:
    geometry = expected_geometry(graph)
    box = geometry.bbox_mm
    size = tuple(
        sorted((box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z)),
    )
    diameters = tuple(sorted(c.radius * 2 for c in geometry.cylinders))
    problems: list[str] = []
    if not _all_close(size, facts.size_mm):
        problems.append(f"size {size} != {facts.size_mm}")
    if not _close(geometry.volume_mm3, facts.volume_mm3):
        problems.append(f"volume {geometry.volume_mm3:.2f} != {facts.volume_mm3:.2f}")
    if not _all_close(diameters, facts.cylinder_diameters_mm):
        problems.append(f"cylinder diameters {diameters} != {facts.cylinder_diameters_mm}")
    return problems


def score(case: Case, answer: Answer) -> list[str]:
    """Return the problems with ``answer`` for ``case``; an empty list means it passes."""
    if case.facts is None:
        return [] if answer is None else ["built a part for a request that must be refused"]
    if answer is None:
        return ["refused a request the MVP supports"]
    graph = parse_part_graph(answer)
    if not isinstance(graph, PartGraph):
        return [f"graph does not parse: {graph}"]
    issues = validate_graph(graph)
    if issues:
        return [f"{issue.pointer}: {issue.message}" for issue in issues]
    return _compare(case.facts, graph)


def score_all(answers: dict[str, Answer]) -> dict[str, list[str]]:
    """Score every case; a missing answer counts as an error."""
    results: dict[str, list[str]] = {}
    for case in CASES:
        if case.case_id not in answers:
            results[case.case_id] = ["no answer given"]
        else:
            results[case.case_id] = score(case, answers[case.case_id])
    return results
