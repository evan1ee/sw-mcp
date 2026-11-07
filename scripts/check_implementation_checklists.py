"""Audit the implementation checklists in ``docs/implementation`` and derive their summary.

The checklist rows are the single source of truth, and the master index defines the conventions.
This script stores neither: it reads the conventions from the index, parses the rows, checks them
for consistency, and prints or rewrites the summary block of the index.

Usage:
    uv run python scripts/check_implementation_checklists.py          # audit, exit 1 on any issue
    uv run python scripts/check_implementation_checklists.py --write  # also refresh the summary
"""

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
IMPL: Final[Path] = ROOT / "docs" / "implementation"
INDEX: Final[Path] = IMPL / "README.md"
BEGIN: Final[str] = (
    "<!-- BEGIN DERIVED SUMMARY (scripts/check_implementation_checklists.py --write) -->"
)
END: Final[str] = "<!-- END DERIVED SUMMARY -->"

RULED_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "Verified",
        "Tested",
        "Implemented",
        "Partially Implemented",
        "Specified",
        "Not Started",
        "Deferred",
        "Under Evaluation",
        "Not Applicable",
    }
)
LAYER_COUNT: Final[int] = 6
LAYER_CELLS: Final[tuple[str, ...]] = ("✅", "◐", "⬜", "N/A")
CATEGORIES: Final[tuple[tuple[str, str], ...]] = (
    ("sketch", "Sketch"),
    ("part-features", "Part Features"),
)

ROW_RE: Final[re.Pattern[str]] = re.compile(
    r"^\| `(?P<id>[A-Z]+-[A-Z]+-\d{3})` \| (?P<name>.+?) \| (?P<scope>[A-Za-z ]+) \| "
    r"(?P<pri>P\d) \| (?P<status>[A-Za-z ]+) \| "
    r"(?P<layers>(?:[^|]+ \| ){5}[^|]+?) \| (?P<note>[^|]*?) ?\|$"
)
FEATURE_RE: Final[re.Pattern[str]] = re.compile(r"^## (?P<id>[A-Z]+-[A-Z]+) — (?P<title>.+)$")
FEATURE_REF_RE: Final[re.Pattern[str]] = re.compile(r"`([A-Z]{2,4}-[A-Z]{3})`")
UNLINKED_REF_RE: Final[re.Pattern[str]] = re.compile(r"(?<!\[)`([A-Z]{2,4}-[A-Z]{3})`(?!\]\()")
ROW_REF_RE: Final[re.Pattern[str]] = re.compile(r"`([A-Z]{2,4}-[A-Z]{3}-\d{3})`")
HOSTS_RE: Final[re.Pattern[str]] = re.compile(r"^\| Depends on \| Hosts: (.+) \|$")
ROW_LIKE_RE: Final[re.Pattern[str]] = re.compile(r"^\|\s*`?[A-Z]+-[A-Z]+-\d+`?\s*\|")
EVIDENCE_REQUIRED: Final[tuple[str, ...]] = ("Verified", "Tested")
LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
TEST_NAME_RE: Final[re.Pattern[str]] = re.compile(r"`(test_[a-z0-9_]+)(?:\.py)?`")
TEST_DEF_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:async )?def (test_\w+)", re.MULTILINE)
SPEC_CITATION_RE: Final[re.Pattern[str]] = re.compile(r"Tier \d|§\d+|\d+\.\d+|K\d+|ADR-\d+|`")
TEST_ROOTS: Final[tuple[str, ...]] = ("tests", "packages", "apps")
TABLE_HEADERS: Final[dict[str, str]] = {
    "status": "| Status | Meaning",
    "scope": "| Scope | Meaning",
    "priority": "| Priority | Meaning",
    "layer": "| Layer | Done means",
    "prefix": "| ID prefix | Owning file",
}


@dataclass(frozen=True, slots=True)
class Row:
    """One checklist row."""

    row_id: str
    scope: str
    pri: str
    status: str
    layers: tuple[str, ...]
    note: str
    feature: str
    path: Path
    line: int


@dataclass(frozen=True, slots=True)
class Conventions:
    """The vocabulary the master index defines; the script holds no copy of it."""

    statuses: tuple[str, ...]
    scopes: tuple[str, ...]
    priorities: tuple[str, ...]
    layers: tuple[str, ...]
    prefixes: tuple[tuple[str, str], ...]


def _table_rows(text: str, header: str) -> list[list[str]]:
    """Cells of the body rows of the Markdown table whose header starts with ``header``."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if line.startswith(header):
            rows: list[list[str]] = []
            for body in lines[number + 2 :]:
                if not body.startswith("|"):
                    break
                rows.append([cell.strip() for cell in body.strip().strip("|").split(" | ")])
            return rows
    return []


def conventions(index_text: str) -> Conventions:
    """Read the status, scope, priority, layer and prefix tables from the index."""

    def first_cells(key: str) -> tuple[str, ...]:
        return tuple(row[0] for row in _table_rows(index_text, TABLE_HEADERS[key]))

    prefixes: list[tuple[str, str]] = []
    for row in _table_rows(index_text, TABLE_HEADERS["prefix"]):
        target = LINK_RE.search(row[-1])
        if target:
            prefixes += [(p, target.group(1)) for p in re.findall(r"`([A-Z-]+)`", row[0])]
    return Conventions(
        first_cells("status"),
        first_cells("scope"),
        first_cells("priority"),
        first_cells("layer"),
        tuple(prefixes),
    )


def convention_problems(conv: Conventions) -> list[str]:
    """The index must define every table, and the script must have a rule for every status."""
    out: list[str] = []
    found = {
        "status": conv.statuses,
        "scope": conv.scopes,
        "priority": conv.priorities,
        "layer": conv.layers,
        "prefix": conv.prefixes,
    }
    out += [f"README.md: {key} table missing" for key, values in found.items() if not values]
    if conv.statuses:
        out += [
            f"README.md: status '{s}' has no rule in the script"
            for s in conv.statuses
            if s not in RULED_STATUSES
        ]
        out += [
            f"script: status rule '{s}' is not in the index"
            for s in sorted(RULED_STATUSES - set(conv.statuses))
        ]
    if conv.layers and len(conv.layers) != LAYER_COUNT:
        out.append(f"README.md: script expects {LAYER_COUNT} layers, index has {len(conv.layers)}")
    return out


def known_tests() -> set[str]:
    """Every Python test function and test module name in the repository."""
    names: set[str] = set()
    for folder in TEST_ROOTS:
        for path in (ROOT / folder).rglob("test_*.py"):
            names.add(path.stem)
            names.update(TEST_DEF_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return names


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    text = re.sub(r"[`*]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """All heading anchors of a Markdown file."""
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6} (.+)$", line)
        if match:
            found.add(slug(match.group(1)))
    return found


def checklist_files() -> list[Path]:
    """Every checklist file (not the master index)."""
    return sorted(p for p in IMPL.rglob("*.md") if p != INDEX)


def parse(files: list[Path]) -> tuple[list[Row], dict[str, Path], list[str]]:
    """Parse rows and features; report malformed table rows."""
    rows: list[Row] = []
    features: dict[str, Path] = {}
    problems: list[str] = []
    for path in files:
        current = ""
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            feature = FEATURE_RE.match(line)
            if feature:
                current = feature.group("id")
                if current in features:
                    problems.append(f"{path.name}:{number}: duplicate feature ID {current}")
                features[current] = path
                continue
            if not ROW_LIKE_RE.match(line):
                continue
            match = ROW_RE.match(line)
            if match is None:
                problems.append(f"{path.name}:{number}: malformed row")
                continue
            layers = tuple(cell.strip() for cell in match.group("layers").split("|"))
            rows.append(
                Row(
                    match.group("id"),
                    match.group("scope"),
                    match.group("pri"),
                    match.group("status"),
                    layers,
                    match.group("note").strip(),
                    current,
                    path,
                    number,
                )
            )
    return rows, features, problems


def ownership_problems(features: dict[str, Path], conv: Conventions) -> list[str]:
    """A feature must live in the file the index names for its ID prefix."""
    out: list[str] = []
    for fid, path in features.items():
        owners = [target for prefix, target in conv.prefixes if fid.startswith(prefix)]
        if not owners:
            out.append(f"{path.name}: {fid} has no ID prefix in the index")
        elif (IMPL / owners[0]).resolve() != path.resolve():
            out.append(f"{path.name}: {fid} belongs in {owners[0]}")
    return out


def host_problems(files: list[Path], rows: list[Row]) -> list[str]:
    """A shared section's ``Hosts`` list must equal the sections whose rows cite it."""
    users: dict[str, set[str]] = {}
    for row in rows:
        for ref in FEATURE_REF_RE.findall(row.note):
            users.setdefault(ref, set()).add(row.feature)
    out: list[str] = []
    for path in files:
        current = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            feature = FEATURE_RE.match(line)
            current = feature.group("id") if feature else current
            hosts = HOSTS_RE.match(line)
            if not hosts:
                continue
            listed = set(FEATURE_REF_RE.findall(hosts.group(1)))
            used = users.get(current, set())
            out += [f"{path.name}: {current}: {f} uses it but is not listed" for f in used - listed]
            out += [f"{path.name}: {current}: {f} is listed but has no row" for f in listed - used]
    return sorted(out)


def structure_problems(rows: list[Row], features: dict[str, Path], files: list[Path]) -> list[str]:
    """Row IDs must belong to their section and run 1..n; files must be in a known folder."""
    out: list[str] = []
    folders = {folder for folder, _ in CATEGORIES}
    out += [f"{p.name}: outside {sorted(folders)}" for p in files if p.parent.name not in folders]
    sequences: dict[str, list[int]] = {fid: [] for fid in features}
    for row in rows:
        prefix, _, number = row.row_id.rpartition("-")
        if prefix != row.feature:
            out.append(f"{row.path.name}:{row.line}: {row.row_id} is not in section {prefix}")
            continue
        sequences[prefix].append(int(number))
    for fid, numbers in sequences.items():
        if not numbers:
            out.append(f"{features[fid].name}: section {fid} has no rows")
        elif sorted(numbers) != list(range(1, len(numbers) + 1)):
            out.append(f"{features[fid].name}: section {fid} has gaps in its row IDs")
    return out


def _note_problems(where: str, row: Row, tests: set[str]) -> list[str]:
    """Notes are never empty; Specified rows cite the spec; Verified and Tested name a test."""
    if not row.note:
        return [f"{where}: {row.status} row needs a note"]
    named = TEST_NAME_RE.findall(row.note)
    out = [f"{where}: unknown test {name}" for name in named if name not in tests]
    if row.status in EVIDENCE_REQUIRED and not named:
        out.append(f"{where}: {row.status} note must name a test")
    if row.status == "Specified" and not SPEC_CITATION_RE.search(row.note):
        out.append(f"{where}: Specified note must cite a spec tier, section or field")
    return out


def row_problems(row: Row, conv: Conventions, tests: set[str]) -> list[str]:
    """Consistency of one row's status, scope, priority, note and layers."""
    where = f"{row.path.name}:{row.line} {row.row_id}"
    out: list[str] = []
    if row.status not in conv.statuses:
        return [f"{where}: unknown status '{row.status}'"]
    if row.scope not in conv.scopes:
        out.append(f"{where}: unknown scope '{row.scope}'")
    if row.pri not in conv.priorities:
        out.append(f"{where}: unknown priority '{row.pri}'")
    out += _note_problems(where, row, tests)
    if len(row.layers) != LAYER_COUNT or any(cell not in LAYER_CELLS for cell in row.layers):
        return [*out, f"{where}: layer cells must be six of {LAYER_CELLS}"]
    done = [cell for cell in row.layers if cell in ("✅", "◐")]
    open_cells = [cell for cell in row.layers if cell == "⬜"]
    out += _status_rules(where, row, done, open_cells)
    if (row.scope == "Out of Scope") != (row.status == "Not Applicable"):
        out.append(f"{where}: Out of Scope must pair with Not Applicable")
    if (row.scope == "Under Evaluation") != (row.status == "Under Evaluation"):
        out.append(f"{where}: Under Evaluation scope must pair with Under Evaluation status")
    return out


def _status_rules(where: str, row: Row, done: list[str], open_cells: list[str]) -> list[str]:
    """Status-versus-layer rules."""
    out: list[str] = []
    if row.status == "Verified" and (open_cells or "◐" in done or row.layers[5] != "✅"):
        out.append(
            f"{where}: Verified needs every applicable layer done, with a passing integration test"
        )
    if row.status == "Tested" and ("✅" not in done or row.layers[5] == "✅"):
        out.append(f"{where}: Tested needs some layers done and no live integration test")
    if row.status == "Implemented" and "✅" not in done:
        out.append(f"{where}: Implemented needs at least one layer done")
    if row.status == "Partially Implemented" and not done:
        out.append(f"{where}: Partially Implemented needs at least one layer done or partial")
    if row.status in ("Specified", "Not Started", "Deferred", "Under Evaluation") and done:
        out.append(f"{where}: {row.status} must not show completed layers")
    if row.status == "Not Applicable" and any(cell != "N/A" for cell in row.layers):
        out.append(f"{where}: Not Applicable rows use N/A in every layer")
    return out


def _link_problems(path: Path, text: str, cache: dict[Path, set[str]]) -> list[str]:
    """Relative links and anchors of one file that do not resolve."""
    out: list[str] = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        file_part, _, fragment = target.partition("#")
        resolved = path if not file_part else (path.parent / file_part).resolve()
        if not resolved.exists():
            out.append(f"{path.name}: broken link {target}")
        elif fragment and resolved.suffix == ".md":
            known = cache.setdefault(resolved, anchors(resolved))
            if fragment not in known:
                out.append(f"{path.name}: missing anchor {target}")
    return out


def reference_problems(
    files: list[Path], features: dict[str, Path], row_ids: set[str], tests: set[str]
) -> list[str]:
    """IDs, tests and relative links that do not resolve, and feature IDs that are not links."""
    out: list[str] = []
    cache: dict[Path, set[str]] = {}
    for path in [*files, INDEX]:
        text = path.read_text(encoding="utf-8")
        for ref in FEATURE_REF_RE.findall(text):
            if ref not in features:
                out.append(f"{path.name}: reference to unknown feature {ref}")
        for ref in ROW_REF_RE.findall(text):
            if ref not in row_ids:
                out.append(f"{path.name}: reference to unknown row {ref}")
        out += [f"{path.name}: {ref} must be a link" for ref in UNLINKED_REF_RE.findall(text)]
        out += _link_problems(path, text, cache)
        if path == INDEX:
            out += [
                f"README.md: unknown test {name}"
                for name in TEST_NAME_RE.findall(text)
                if name not in tests
            ]
    return out


def duplicate_problems(rows: list[Row]) -> list[str]:
    """Row IDs must be unique."""
    counts = Counter(row.row_id for row in rows)
    return [f"duplicate row ID {rid}" for rid, n in counts.items() if n > 1]


def summary(rows: list[Row], features: dict[str, Path], conv: Conventions) -> str:
    """Markdown summary derived from the rows, in the order the index defines."""
    header = "| Category | Capabilities | Items | " + " | ".join(conv.statuses) + " |"
    divider = "|---|---:|---:|" + "---:|" * len(conv.statuses)
    lines = [header, divider]
    totals: Counter[str] = Counter()
    total_items = 0
    total_caps = 0
    for folder, label in CATEGORIES:
        mine = [r for r in rows if r.path.parent.name == folder]
        caps = sum(1 for p in features.values() if p.parent.name == folder)
        counts = Counter(r.status for r in mine)
        totals.update(counts)
        total_items += len(mine)
        total_caps += caps
        cells = " | ".join(str(counts[s]) for s in conv.statuses)
        lines.append(f"| {label} | {caps} | {len(mine)} | {cells} |")
    lines.append(
        f"| **Total** | **{total_caps}** | **{total_items}** | "
        + " | ".join(f"**{totals[s]}**" for s in conv.statuses)
        + " |"
    )
    scope = Counter(r.scope for r in rows)
    pri = Counter(r.pri for r in rows)
    lines += [
        "",
        "| Scope | " + " | ".join(conv.scopes) + " |",
        "|---|" + "---:|" * len(conv.scopes),
        "| Items | " + " | ".join(str(scope[s]) for s in conv.scopes) + " |",
        "",
        "| Priority | " + " | ".join(conv.priorities) + " |",
        "|---|" + "---:|" * len(conv.priorities),
        "| Items | " + " | ".join(str(pri[p]) for p in conv.priorities) + " |",
        "",
        "| Document | Capabilities | Items | Verified | Tested | Partially Implemented |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for path in checklist_files():
        mine = [r for r in rows if r.path == path]
        caps = sum(1 for p in features.values() if p == path)
        counts = Counter(r.status for r in mine)
        rel = path.relative_to(IMPL).as_posix()
        lines.append(
            f"| [{rel}]({rel}) | {caps} | {len(mine)} | {counts['Verified']} | {counts['Tested']} |"
            f" {counts['Partially Implemented']} |"
        )
    return "\n".join(lines)


def splice(index_text: str, block: str) -> str:
    """Replace the derived block in the index text."""
    start = index_text.index(BEGIN) + len(BEGIN)
    stop = index_text.index(END)
    return index_text[:start] + "\n" + block + "\n" + index_text[stop:]


def audit() -> tuple[list[Row], dict[str, Path], list[str]]:
    """Parse the checklists and return every problem except summary staleness."""
    conv = conventions(INDEX.read_text(encoding="utf-8"))
    tests = known_tests()
    files = checklist_files()
    rows, features, problems = parse(files)
    problems += convention_problems(conv)
    for row in rows:
        problems += row_problems(row, conv, tests)
    problems += duplicate_problems(rows)
    problems += structure_problems(rows, features, files)
    problems += ownership_problems(features, conv)
    problems += host_problems(files, rows)
    problems += reference_problems(files, features, {row.row_id for row in rows}, tests)
    return rows, features, problems


def main(argv: list[str]) -> int:
    """Run the audit; return a process exit code."""
    rows, features, problems = audit()
    index_text = INDEX.read_text(encoding="utf-8")
    block = summary(rows, features, conventions(index_text))
    if BEGIN not in index_text or END not in index_text:
        problems.append("README.md: derived summary markers missing")
    elif "--write" in argv:
        INDEX.write_text(splice(index_text, block), encoding="utf-8")
    elif splice(index_text, block) != index_text:
        problems.append("README.md: derived summary is stale (run with --write)")
    for problem in problems:
        print(problem)
    print(f"{len(rows)} items, {len(features)} capabilities, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
