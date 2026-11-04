"""Helpers for the cad-protocol tests: shared transcripts and inline transcript building."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ipc"
TOKEN = "tok-5f2c91d7"

type Frame = dict[str, Any]
# (direction, t_ms, frame): direction is "c2a" (core to add-in), "a2c", or "close" (frame None).
type Entry = tuple[str, int, Frame | None]

_DIRECTIONS = {"c2a": "core_to_addin", "a2c": "addin_to_core", "close": "addin_to_core"}


def _entry_line(entry: Entry) -> str:
    direction, t_ms, frame = entry
    line: dict[str, Any] = {"dir": _DIRECTIONS[direction], "t_ms": t_ms}
    if direction == "close":
        line["close"] = True
    else:
        line["frame"] = frame
    return json.dumps(line, ensure_ascii=False)


def build_transcript(entries: Sequence[Entry], config: dict[str, Any] | None = None) -> str:
    header = {
        "transcript": "0.1",
        "scenario": "inline",
        "source": "synthetic",
        "sides": ["python"],
        "config": {"token": TOKEN, **(config or {})},
    }
    lines = [json.dumps(header), *(_entry_line(e) for e in entries)]
    return "\n".join(lines) + "\n"


@pytest.fixture
def fixture_text() -> Callable[[str], str]:
    """The text of ``tests/fixtures/ipc/<name>.jsonl``."""

    def read(name: str) -> str:
        return (FIXTURES / f"{name}.jsonl").read_text(encoding="utf-8")

    return read


@pytest.fixture
def make_transcript() -> Callable[..., str]:
    """``make_transcript(entries, config=None)``: JSON Lines text for an in-code scenario."""
    return build_transcript
