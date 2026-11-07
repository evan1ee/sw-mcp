"""Tests for the implementation checklist audit script (docs/implementation)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_implementation_checklists.py"
GOOD_ROW = (
    "| `AB-CDE-001` | Blind | In Scope | P0 | Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `test_x` |"
)
LAYERS_OPEN = "⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_implementation_checklists", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_script()


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A minimal checklist tree the script is pointed at."""
    (tmp_path / "sketch").mkdir()
    (tmp_path / "part-features").mkdir()
    (tmp_path / "README.md").write_text(f"{CHECKER.BEGIN}\n{CHECKER.END}\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "IMPL", tmp_path)
    monkeypatch.setattr(CHECKER, "INDEX", tmp_path / "README.md")
    return tmp_path


def _problems(tree: Path, *rows: str, heading: str = "## AB-CDE — Title") -> list[str]:
    body = "\n".join([heading, "", *rows, ""])
    (tree / "sketch" / "a.md").write_text(body, encoding="utf-8")
    _, _, problems = CHECKER.audit()
    return problems


def test_real_checklists_are_clean() -> None:
    assert CHECKER.main([]) == 0


def test_good_row_passes(tree: Path) -> None:
    assert _problems(tree, GOOD_ROW) == []


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (GOOD_ROW.replace("Verified", "Verifiedd"), "unknown status"),
        (GOOD_ROW.replace("| P0 |", "| P9 |"), "unknown priority"),
        (GOOD_ROW.replace("In Scope", "Sideways"), "unknown scope"),
        (GOOD_ROW.replace("`test_x` |", "|"), "needs evidence"),
        (GOOD_ROW.replace("`AB-CDE-001`", "AB-CDE-001"), "malformed"),
        (GOOD_ROW.replace("`test_x`", "a | b"), "malformed"),
        (GOOD_ROW.replace("| ✅ | `test_x`", "| ⬜ | `test_x`"), "Verified needs"),
        (GOOD_ROW.replace("`AB-CDE-001`", "`ZZ-ZZZ-001`"), "is not in section"),
        (GOOD_ROW.replace("`AB-CDE-001`", "`AB-CDE-002`"), "gaps"),
        (
            "| `AB-CDE-001` | n | In Scope | P1 | Tested | ◐ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | t |",
            "Tested needs",
        ),
        (
            "| `AB-CDE-001` | n | In Scope | P1 | Implemented | ◐ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | t |",
            "Implemented",
        ),
        (
            "| `AB-CDE-001` | n | In Scope | P1 | Specified | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | 5.3 |",
            "completed",
        ),
        (
            f"| `AB-CDE-001` | n | Out of Scope | P3 | Deferred | {LAYERS_OPEN} | 5.3 |",
            "Out of Scope",
        ),
    ],
)
def test_bad_rows_are_reported(tree: Path, row: str, expected: str) -> None:
    assert any(expected in problem for problem in _problems(tree, row))


def test_duplicate_row_id(tree: Path) -> None:
    assert any("duplicate row ID" in p for p in _problems(tree, GOOD_ROW, GOOD_ROW))


def test_section_without_rows(tree: Path) -> None:
    assert any("has no rows" in p for p in _problems(tree))


def test_unknown_references(tree: Path) -> None:
    row = GOOD_ROW.replace("`test_x`", "`SK-ZZZ`, `SK-ZZZ-999`")
    problems = _problems(tree, row)
    assert any("unknown feature SK-ZZZ" in p for p in problems)
    assert any("unknown row SK-ZZZ-999" in p for p in problems)


def test_broken_link(tree: Path) -> None:
    row = GOOD_ROW.replace("`test_x`", "[x](missing.md)")
    assert any("broken link" in p for p in _problems(tree, row))


def test_file_outside_known_folders(tree: Path) -> None:
    (tree / "other").mkdir()
    (tree / "other" / "x.md").write_text("", encoding="utf-8")
    assert any("outside" in p for p in _problems(tree, GOOD_ROW))


def test_stale_summary_fails_and_write_refreshes(tree: Path) -> None:
    (tree / "sketch" / "a.md").write_text(f"## AB-CDE — T\n\n{GOOD_ROW}\n", encoding="utf-8")
    assert CHECKER.main([]) == 1
    assert CHECKER.main(["--write"]) == 0
    assert CHECKER.main([]) == 0
