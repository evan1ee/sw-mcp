"""The tool table of 12.4.4 and the contract files agree; CI checks it (spec 12.4.4)."""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from cad_application.testing.tool_rig import make_tool_rig
from cad_application.tools.contracts import ToolContract, load_contracts
from cad_ir.generated.error_codes import ErrorCode

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "docs" / "api" / "tool-contracts.md"
SHIPPED_PHASES = {"1a"}
SHIPPED_TOOLS = {
    "apply_part_graph",
    "validate_part_graph",
    "list_feature_types",
    "get_feature_schema",
}
HEADING = "### 12.4.4 Tool table"
CELLS = 5
ROW = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|")


@dataclass(frozen=True, slots=True)
class Row:
    toolset: str
    phase: str
    kind: str
    mutates: bool


@dataclass(frozen=True, slots=True)
class Table:
    rows: Mapping[str, Row]
    problems: tuple[str, ...]


def parse_table(text: str) -> Table:
    """The rows of the 12.4.4 table by tool name; unreadable rows and repeats are problems."""
    rows: dict[str, Row] = {}
    problems: list[str] = []
    inside = found_heading = False
    for line in text.splitlines():
        if line.startswith("### "):
            inside = line.strip() == HEADING
            found_heading = found_heading or inside
            continue
        match = ROW.match(line) if inside else None
        if match is None:
            continue
        name, cells = match.group(1), [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != CELLS:
            problems.append(f"{name}: the row has {len(cells)} cells, not {CELLS}")
        elif name in rows:
            problems.append(f"{name}: the row appears twice")
        else:
            rows[name] = Row(cells[1], cells[2], cells[3], cells[4].startswith("yes"))
    if not found_heading:
        problems.append(f"no tool table: the heading {HEADING!r} is missing")
    return Table(rows, tuple(problems))


def _row_problems(name: str, row: Row, contract: ToolContract) -> list[str]:
    same = {
        "toolset": (row.toolset, contract.toolset),
        "phase": (row.phase, contract.phase),
        "kind": (row.kind, contract.kind),
        "mutates": (row.mutates, contract.mutates),
    }
    return [
        f"{name}: {field} is {table!r} in the table and {file!r} in the contract file"
        for field, (table, file) in same.items()
        if table != file
    ]


def table_problems(
    table: Table,
    contracts: Mapping[str, ToolContract],
    shipped: Collection[str],
    shipped_tools: Collection[str] = SHIPPED_TOOLS,
) -> list[str]:
    """Every difference between the table and the contract files (12.4.4)."""
    problems = list(table.problems)
    for name, contract in contracts.items():
        row = table.rows.get(name)
        if row is None:
            problems.append(f"{name}: a contract file exists but the table has no row")
        else:
            problems += _row_problems(name, row, contract)
    for name, row in table.rows.items():
        if (row.phase in shipped or name in shipped_tools) and name not in contracts:
            problems.append(f"{name}: no contract file for a row of shipped phase {row.phase}")
    return problems


def _problems(text: str) -> list[str]:
    return table_problems(parse_table(text), load_contracts(), SHIPPED_PHASES, SHIPPED_TOOLS)


def test_table_matches_contract_files() -> None:
    assert _problems(TABLE.read_text(encoding="utf-8")) == []


def test_every_shipped_tool_registered() -> None:
    rows = parse_table(TABLE.read_text(encoding="utf-8")).rows
    shipped = {
        name for name, row in rows.items() if row.phase in SHIPPED_PHASES or name in SHIPPED_TOOLS
    }
    assert shipped
    assert set(make_tool_rig().registry.names) == shipped


def test_contract_errors_are_catalogued() -> None:
    catalogue = {code.value for code in ErrorCode}
    for name, contract in load_contracts().items():
        unknown = [code for code in contract.errors if code not in catalogue]
        assert unknown == [], name


def _broken(tmp_path: Path, old: str, new: str) -> str:
    """A temporary copy of the table with ``old`` replaced by ``new`` (it must be there)."""
    original = TABLE.read_text(encoding="utf-8")
    assert old in original, old
    copy = tmp_path / "tool-contracts.md"
    copy.write_text(original.replace(old, new, 1), encoding="utf-8")
    return copy.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("| `check_drawing` | drawing |", "| `check_drawing` | core |", "check_drawing: toolset"),
        (
            "| `check_drawing` | drawing | 1a |",
            "| `check_drawing` | drawing | 1b |",
            "check_drawing: phase",
        ),
        ("| 1a | job | no (reads", "| 1a | store | no (reads", "check_drawing: kind"),
        (
            "| `cancel_execution` | core | 1a | store | yes (job) |",
            "| `cancel_execution` | core | 1a | store | no |",
            "cancel_execution: mutates",
        ),
        (
            "| `get_drawing_report` | drawing | 1a | store | no |\n",
            "",
            "get_drawing_report: a contract file exists but the table has no row",
        ),
        (
            "| `list_cad_files` | core | 1b | store | no |",
            "| `list_cad_files` | core | 1a | store | no |",
            "list_cad_files: no contract file for a row of shipped phase 1a",
        ),
        (
            "| `get_execution_status` | core |",
            "| `get_execution_status` | core | extra |",
            "get_execution_status: the row has 6 cells",
        ),
    ],
)
def test_table_check_detects_mismatch(tmp_path: Path, old: str, new: str, expected: str) -> None:
    problems = _problems(_broken(tmp_path, old, new))
    assert any(expected in problem for problem in problems), problems


def test_table_check_detects_a_duplicate_row_and_a_missing_table(tmp_path: Path) -> None:
    row = "| `get_execution_status` | core | 1a | store | no |"
    duplicated = _broken(tmp_path, row, row + "\n" + row)
    assert any("twice" in problem for problem in _problems(duplicated))
    assert any("no tool table" in problem for problem in _problems("# nothing here\n"))
