"""Tests for the implementation checklist audit script (docs/implementation)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_implementation_checklists.py"
REAL_TEST = "test_good_row_passes"
GOOD_ROW = (
    "| `AB-CDE-001` | Blind | In Scope | P0 | Verified "
    f"| ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `{REAL_TEST}` |"
)
LAYERS_OPEN = "⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜"
SPECIFIED_ROW = f"| `AB-CDE-001` | n | In Scope | P1 | Specified | {LAYERS_OPEN} | 5.3 |"
STATUS_TABLE = """| Status | Meaning | Layer rule enforced |
| --- | --- | --- |
| Not Started | a | b |
| Specified | a | b |
| Partially Implemented | a | b |
| Implemented | a | b |
| Tested | a | b |
| Verified | a | b |
| Deferred | a | b |
| Under Evaluation | a | b |
| Not Applicable | a | b |
"""
PRIORITY_TABLE = """| Priority | Meaning |
| --- | --- |
| P0 | a |
| P1 | a |
| P2 | a |
| P3 | a |
"""


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_implementation_checklists", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_script()


def _index(status_table: str = STATUS_TABLE, priority_table: str = PRIORITY_TABLE) -> str:
    return f"""| ID prefix | Owning file |
| --- | --- |
| `AB-` | [a](sketch/a.md) |
| `CD-` | [b](part-features/b.md) |

{status_table}
| Scope | Meaning |
| --- | --- |
| In Scope | a |
| Out of Scope | a |
| Under Evaluation | a |

{priority_table}
| Layer | Done means |
| --- | --- |
| IR | a |
| Compiler | a |
| Adapter | a |
| Execution | a |
| Validation | a |
| Integration Test | a |

{CHECKER.BEGIN}
{CHECKER.END}
"""


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A minimal checklist tree the script is pointed at."""
    (tmp_path / "sketch").mkdir()
    (tmp_path / "part-features").mkdir()
    (tmp_path / "part-features" / "b.md").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text(_index(), encoding="utf-8")
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
        (GOOD_ROW.replace(f"`{REAL_TEST}` |", "|"), "needs a note"),
        (GOOD_ROW.replace(f"`{REAL_TEST}`", "Plate"), "must name a test"),
        (GOOD_ROW.replace(REAL_TEST, "test_no_such_test_anywhere"), "unknown test"),
        (GOOD_ROW.replace("`AB-CDE-001`", "AB-CDE-001"), "malformed"),
        (GOOD_ROW.replace(f"`{REAL_TEST}`", "a | b"), "malformed"),
        (GOOD_ROW.replace(f"| ✅ | `{REAL_TEST}`", f"| ⬜ | `{REAL_TEST}`"), "Verified needs"),
        (GOOD_ROW.replace("`AB-CDE-001`", "`ZZ-ZZZ-001`"), "is not in section"),
        (GOOD_ROW.replace("`AB-CDE-001`", "`AB-CDE-002`"), "gaps"),
        (
            GOOD_ROW.replace(
                "| Verified | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |",
                "| Tested | ◐ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |",
            ),
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
        (SPECIFIED_ROW.replace("| 5.3 |", "|  |"), "needs a note"),
        (SPECIFIED_ROW.replace("| 5.3 |", "| Degrees |"), "must cite"),
    ],
)
def test_bad_rows_are_reported(tree: Path, row: str, expected: str) -> None:
    assert any(expected in problem for problem in _problems(tree, row))


@pytest.mark.parametrize("note", ["5.3.2", "§9", "Tier 2", "K23", "ADR-066", "`field`"])
def test_specified_citations_are_accepted(tree: Path, note: str) -> None:
    assert _problems(tree, SPECIFIED_ROW.replace("5.3", note)) == []


def test_duplicate_row_id(tree: Path) -> None:
    assert any("duplicate row ID" in p for p in _problems(tree, GOOD_ROW, GOOD_ROW))


def test_section_without_rows(tree: Path) -> None:
    assert any("has no rows" in p for p in _problems(tree))


def test_unknown_references(tree: Path) -> None:
    row = GOOD_ROW.replace(f"`{REAL_TEST}`", f"`{REAL_TEST}`, `SK-ZZZ`, `SK-ZZZ-999`")
    problems = _problems(tree, row)
    assert any("unknown feature SK-ZZZ" in p for p in problems)
    assert any("unknown row SK-ZZZ-999" in p for p in problems)


def test_reference_with_an_unlisted_prefix_is_reported(tree: Path) -> None:
    row = GOOD_ROW.replace(f"`{REAL_TEST}`", f"`{REAL_TEST}`, `ZZ-THN`")
    assert any("unknown feature ZZ-THN" in p for p in _problems(tree, row))


def test_feature_reference_must_be_a_link(tree: Path) -> None:
    (tree / "part-features" / "b.md").write_text(
        f"## CD-EFG — Other\n\n{SPECIFIED_ROW.replace('AB-CDE', 'CD-EFG')}\n", encoding="utf-8"
    )
    bare = SPECIFIED_ROW.replace("| 5.3 |", "| 5.3; `CD-EFG` |")
    assert any("CD-EFG must be a link" in p for p in _problems(tree, bare))
    linked = bare.replace("`CD-EFG`", "[`CD-EFG`](../part-features/b.md#cd-efg--other)")
    assert _problems(tree, linked) == []


def test_feature_in_the_wrong_file_is_reported(tree: Path) -> None:
    row = SPECIFIED_ROW.replace("AB-CDE", "CD-EFG")
    assert any("belongs in" in p for p in _problems(tree, row, heading="## CD-EFG — Title"))


def test_feature_without_a_listed_prefix_is_reported(tree: Path) -> None:
    row = SPECIFIED_ROW.replace("AB-CDE", "ZZ-NEW")
    assert any("no ID prefix" in p for p in _problems(tree, row, heading="## ZZ-NEW — Title"))


def test_shared_hosts_must_match_the_rows_that_use_the_owner(tree: Path) -> None:
    owner = (
        f"## AB-OWN — Owner\n\n{SPECIFIED_ROW.replace('AB-CDE', 'AB-OWN')}\n\n"
        "| Depends on | Hosts: `AB-HST`, `AB-GON` |\n\n"
    )
    host = SPECIFIED_ROW.replace("AB-CDE", "AB-HST").replace("| 5.3 |", "| 5.3; `AB-OWN` |")
    other = SPECIFIED_ROW.replace("AB-CDE", "AB-XTR").replace("| 5.3 |", "| 5.3; `AB-OWN` |")
    gone = SPECIFIED_ROW.replace("AB-CDE", "AB-GON")
    body = (
        f"{owner}## AB-HST — H\n\n{host}\n\n## AB-XTR — X\n\n{other}\n\n## AB-GON — G\n\n{gone}\n"
    )
    (tree / "sketch" / "a.md").write_text(body, encoding="utf-8")
    _, _, problems = CHECKER.audit()
    assert any("AB-OWN" in p and "AB-XTR" in p and "not listed" in p for p in problems)
    assert any("AB-OWN" in p and "AB-GON" in p and "no row" in p for p in problems)


def test_broken_link(tree: Path) -> None:
    row = GOOD_ROW.replace(f"`{REAL_TEST}`", f"`{REAL_TEST}`, [x](missing.md)")
    assert any("broken link" in p for p in _problems(tree, row))


def test_file_outside_known_folders(tree: Path) -> None:
    (tree / "other").mkdir()
    (tree / "other" / "x.md").write_text("", encoding="utf-8")
    assert any("outside" in p for p in _problems(tree, GOOD_ROW))


def test_statuses_come_from_the_index(tree: Path) -> None:
    renamed = STATUS_TABLE.replace("| Tested |", "| Unit Tested |")
    (tree / "README.md").write_text(_index(status_table=renamed), encoding="utf-8")
    problems = _problems(tree, GOOD_ROW.replace("Verified", "Unit Tested"))
    assert any("Unit Tested" in p and "no rule" in p for p in problems)
    assert any("Tested" in p and "not in the index" in p for p in problems)


def test_priorities_come_from_the_index(tree: Path) -> None:
    fewer = PRIORITY_TABLE.replace("| P3 | a |\n", "")
    (tree / "README.md").write_text(_index(priority_table=fewer), encoding="utf-8")
    row = f"| `AB-CDE-001` | n | In Scope | P3 | Deferred | {LAYERS_OPEN} | 5.3 |"
    assert any("unknown priority" in p for p in _problems(tree, row))


def test_missing_convention_table_is_reported(tree: Path) -> None:
    (tree / "README.md").write_text(f"{CHECKER.BEGIN}\n{CHECKER.END}\n", encoding="utf-8")
    assert any("table missing" in p for p in _problems(tree, GOOD_ROW))


def test_summary_columns_follow_the_index(tree: Path) -> None:
    (tree / "sketch" / "a.md").write_text(f"## AB-CDE — T\n\n{GOOD_ROW}\n", encoding="utf-8")
    assert CHECKER.main(["--write"]) == 0
    text = (tree / "README.md").read_text(encoding="utf-8")
    assert "| Category | Capabilities | Items | Not Started | Specified |" in text


def test_stale_summary_fails_and_write_refreshes(tree: Path) -> None:
    (tree / "sketch" / "a.md").write_text(f"## AB-CDE — T\n\n{GOOD_ROW}\n", encoding="utf-8")
    assert CHECKER.main([]) == 1
    assert CHECKER.main(["--write"]) == 0
    assert CHECKER.main([]) == 0
