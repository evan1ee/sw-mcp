"""Shared fixtures: drawing snapshots read from the schema fixtures (tests may read files)."""

import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from cad_ir.core.json_types import JsonValue

SNAPSHOTS = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "schemas"
    / "drawing-geometry-snapshot"
    / "valid"
)


def _load(name: str) -> dict[str, JsonValue]:
    doc: dict[str, JsonValue] = json.loads((SNAPSHOTS / f"{name}.json").read_text(encoding="utf-8"))
    return doc


@pytest.fixture
def good_snapshot() -> dict[str, JsonValue]:
    """A valid snapshot whose verdict is ``not_evaluated``."""
    return _load("checks_data")


@pytest.fixture
def failing_snapshot() -> dict[str, JsonValue]:
    """A valid snapshot whose rebuild reports a dangling dimension (D10 fails)."""
    doc = copy.deepcopy(_load("checks_data"))
    doc["rebuild"] = {
        "completed": True,
        "errors": [
            {
                "kind": "dangling",
                "sheet": "s_0123456789",
                "annotation": "dim_width",
                "message": "dimension lost its reference",
            }
        ],
        "silhouette_attachments": [],
        "reopen": "verified",
    }
    return doc


@pytest.fixture
def snapshot_loader() -> Callable[[str], dict[str, JsonValue]]:
    return _load
