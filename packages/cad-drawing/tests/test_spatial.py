"""Uniform-grid candidate pairs (plan Task 4)."""

import itertools
import random

import pytest
from cad_drawing.checks.geometry2d import Segment, segment_distance
from cad_drawing.checks.primitives import Prim
from cad_drawing.checks.spatial import GridIndex

COUNT = 200
EXTENT = 100.0


def everything(_: Prim) -> bool:
    return True


def seg_prim(i: int, s: Segment) -> Prim:
    return Prim("edge", f"v{i:03d}", (s,), None, None, None, 0)


def random_prims() -> list[Prim]:
    rng = random.Random(7)
    prims: list[Prim] = []
    for i in range(COUNT):
        x, y = rng.uniform(0, EXTENT), rng.uniform(0, EXTENT)
        prims.append(seg_prim(i, Segment((x, y), (x + rng.uniform(-8, 8), y + rng.uniform(-8, 8)))))
    return prims


def test_grid_pairs_match_bruteforce() -> None:
    prims = random_prims()
    index = GridIndex.build(prims)
    pairs = list(index.candidate_pairs(everything, None, 1.0))
    keys = [frozenset((id(p), id(q))) for p, q in pairs]
    assert len(keys) == len(set(keys))  # each unordered pair exactly once
    near = {k for (p, q), k in zip(pairs, keys, strict=True) if _dist(p, q) <= 1.0}
    brute = {
        frozenset((id(p), id(q))) for p, q in itertools.combinations(prims, 2) if _dist(p, q) <= 1.0
    }
    assert near == brute
    assert brute  # the seed produces close pairs, so the comparison is not vacuous


def _dist(p: Prim, q: Prim) -> float:
    return segment_distance(p.segments[0], q.segments[0])


def test_grid_pairs_are_deterministic() -> None:
    prims = random_prims()
    first = [
        (p.owner, q.owner) for p, q in GridIndex.build(prims).candidate_pairs(everything, None, 1.0)
    ]
    again = [
        (p.owner, q.owner) for p, q in GridIndex.build(prims).candidate_pairs(everything, None, 1.0)
    ]
    assert first == again


def test_two_sets_pair_across_only() -> None:
    prims = [
        seg_prim(0, Segment((0, 0), (1, 0))),
        seg_prim(1, Segment((0, 0.5), (1, 0.5))),
        seg_prim(2, Segment((0, 1), (1, 1))),
    ]
    index = GridIndex.build(prims)
    pairs = list(
        index.candidate_pairs(lambda p: p.owner == "v000", lambda p: p.owner != "v000", 1.0)
    )
    assert [(p.owner, q.owner) for p, q in pairs] == [("v000", "v001"), ("v000", "v002")]


def test_far_apart_and_empty_prims_give_no_pairs() -> None:
    prims = [
        seg_prim(0, Segment((0, 0), (1, 0))),
        seg_prim(1, Segment((500, 500), (501, 500))),
        Prim("dimension_line", "empty", (), None, None, None, 0),
    ]
    assert list(GridIndex.build(prims).candidate_pairs(everything, None, 1.0)) == []


def test_cells_cannot_be_modified() -> None:
    index = GridIndex.build([seg_prim(0, Segment((0, 0), (1, 0)))])
    with pytest.raises(TypeError):
        index.cells[(0, 0)] = ()  # type: ignore[index]  # pyright: ignore[reportIndexIssue]


def test_the_same_prim_listed_twice_pairs_by_position() -> None:
    p = seg_prim(0, Segment((0, 0), (1, 0)))
    pairs = list(GridIndex.build([p, p]).candidate_pairs(everything, None, 1.0))
    assert pairs == [(p, p)]
