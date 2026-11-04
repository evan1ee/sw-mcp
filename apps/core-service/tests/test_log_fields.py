"""Every field the code emits reaches the log file (G3, register J20)."""

import ast
from pathlib import Path

from core_service.jsonl_log import ALLOWED_FIELDS

ROOT = Path(__file__).resolve().parents[3]
SOURCES = (ROOT / "packages" / "cad-application" / "src", ROOT / "apps" / "core-service" / "src")
FIXED = {"event", "level"}  # the positional parameters of ``emit``


def _emitted_fields() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for base in SOURCES:
        for path in base.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                is_emit = isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "emit"
                if is_emit and isinstance(node, ast.Call):
                    names = {k.arg for k in node.keywords if k.arg is not None} - FIXED
                    found.setdefault(path.name, set()).update(names)
    return found


def test_every_emit_field_allowed() -> None:
    found = _emitted_fields()
    assert found  # the scan found the emit calls at all
    dropped = {name: sorted(f - ALLOWED_FIELDS) for name, f in found.items() if f - ALLOWED_FIELDS}
    assert dropped == {}


def test_store_is_an_allowed_field() -> None:
    assert "store" in ALLOWED_FIELDS
