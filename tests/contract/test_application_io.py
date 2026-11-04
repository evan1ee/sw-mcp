"""cad_application performs no direct I/O (guideline G2): every effect goes through a port."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "packages" / "cad-application" / "src"
BANNED_MODULES = {"os", "pathlib", "shutil", "tempfile", "msvcrt", "time", "secrets", "random"}
BANNED_BUILTINS = {"open"}
BANNED_CLOCK_CALLS = {"now", "utcnow", "today"}


def _violations(source: str, name: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [
                f"{name}:{node.lineno} import {a.name}"
                for a in node.names
                if a.name.split(".")[0] in BANNED_MODULES
            ]
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BANNED_MODULES:
                found.append(f"{name}:{node.lineno} from {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_BUILTINS:
                found.append(f"{name}:{node.lineno} {func.id}()")
            elif isinstance(func, ast.Attribute) and func.attr in BANNED_CLOCK_CALLS:
                owner = ast.unparse(func.value)
                if owner in {"datetime", "datetime.datetime", "date"}:
                    found.append(f"{name}:{node.lineno} {owner}.{func.attr}()")
    return found


def test_cad_application_has_no_direct_io() -> None:
    files = sorted(SRC.rglob("*.py"))
    assert files
    problems = [v for f in files for v in _violations(f.read_text("utf-8"), f.name)]
    assert problems == []


def test_the_scanner_detects_each_kind_of_violation() -> None:
    bad = (
        "import os\nfrom pathlib import Path\nimport datetime\n"
        "open('x')\ndatetime.datetime.now()\nimport time\n"
    )
    assert len(_violations(bad, "bad.py")) == 5  # noqa: PLR2004
    assert _violations("import threading, hashlib, json\n", "ok.py") == []
