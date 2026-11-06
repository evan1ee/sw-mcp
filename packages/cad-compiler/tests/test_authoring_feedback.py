"""Validator messages tell an agent what to change, so it can repair a graph in one step."""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cad_compiler.validator.semantic import validate_graph
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph

ROOT = Path(__file__).resolve().parents[3]
PLATE = ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid" / "plate_4h.json"

Mutation = Callable[[dict[str, Any]], None]


def _second_extrude(raw: dict[str, Any]) -> None:
    raw["nodes"]["extrude_two"] = {
        "type": "extrude",
        "dependencies": ["sketch_base"],
        "profile": "sketch_base",
        "end_condition": {"type": "blind", "depth": 5},
    }


def _cut_without_extrude(raw: dict[str, Any]) -> None:
    raw["nodes"]["cut_holes"]["dependencies"] = ["sketch_holes"]


def _open_loop(raw: dict[str, Any]) -> None:
    del raw["nodes"]["sketch_base"]["entities"]["l4"]


def _hole_on_edge(raw: dict[str, Any]) -> None:
    raw["nodes"]["sketch_holes"]["entities"]["c1"]["center"] = [-50, -20]


CASES: list[tuple[str, Mutation, str]] = [
    ("second_extrude", _second_extrude, "remove the extra extrude"),
    ("cut_without_extrude", _cut_without_extrude, "add the extrude"),
    ("open_loop", _open_loop, "end point must meet"),
    ("hole_on_edge", _hole_on_edge, "move it inside"),
]


@pytest.mark.parametrize(("name", "mutate", "hint"), CASES, ids=[c[0] for c in CASES])
def test_message_says_how_to_fix(name: str, mutate: Mutation, hint: str) -> None:
    raw = copy.deepcopy(json.loads(PLATE.read_text(encoding="utf-8")))
    mutate(raw)
    graph = parse_part_graph(raw)
    assert isinstance(graph, PartGraph), name
    messages = " | ".join(issue.message for issue in validate_graph(graph))
    assert hint in messages, messages
