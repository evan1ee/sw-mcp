"""Audit the implementation checklists in ``docs/implementation`` and derive their summary.

The checklist rows are the single source of truth. This script never stores state: it parses the
rows, checks them for consistency, and prints or rewrites the summary block of the master index.

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

STATUSES: Final[tuple[str, ...]] = (
    "Verified",
    "Tested",
    "Implemented",
    "Partially Implemented",
    "Specified",
    "Not Started",
    "Deferred",
    "Under Evaluation",
    "Not Applicable",
)
SCOPES: Final[tuple[str, ...]] = ("In Scope", "Out of Scope", "Under Evaluation")
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
FEATURE_REF_RE: Final[re.Pattern[str]] = re.compile(
    r"`((?:SK|BF|CF|SHP|HT|PAT|RG|SRF|SMT|MBD|CM|ADV)-[A-Z]{3})`"
)
ROW_REF_RE: Final[re.Pattern[str]] = re.compile(
    r"`((?:SK|BF|CF|SHP|HT|PAT|RG|SRF|SMT|MBD|CM|ADV)-[A-Z]{3}-\d{3})`"
)
ROW_LIKE_RE: Final[re.Pattern[str]] = re.compile(r"^\|\s*`?[A-Z]+-[A-Z]+-\d+`?\s*\|")
PRIORITIES: Final[tuple[str, ...]] = ("P0", "P1", "P2", "P3")
EVIDENCE_REQUIRED: Final[tuple[str, ...]] = ("Verified", "Tested")
LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


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


def row_problems(row: Row) -> list[str]:
    """Consistency of one row's status, scope, priority and layers."""
    where = f"{row.path.name}:{row.line} {row.row_id}"
    out: list[str] = []
    if row.status not in STATUSES:
        return [f"{where}: unknown status '{row.status}'"]
    if row.scope not in SCOPES:
        out.append(f"{where}: unknown scope '{row.scope}'")
    if row.pri not in PRIORITIES:
        out.append(f"{where}: unknown priority '{row.pri}'")
    if row.status in EVIDENCE_REQUIRED and not row.note:
        out.append(f"{where}: {row.status} needs evidence in Notes")
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


def reference_problems(
    files: list[Path], features: dict[str, Path], row_ids: set[str]
) -> list[str]:
    """Feature and row references and relative links that do not resolve."""
    out: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for path in [*files, INDEX]:
        text = path.read_text(encoding="utf-8")
        for ref in FEATURE_REF_RE.findall(text):
            if ref not in features:
                out.append(f"{path.name}: reference to unknown feature {ref}")
        for ref in ROW_REF_RE.findall(text):
            if ref not in row_ids:
                out.append(f"{path.name}: reference to unknown row {ref}")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, fragment = target.partition("#")
            resolved = path if not file_part else (path.parent / file_part).resolve()
            if not resolved.exists():
                out.append(f"{path.name}: broken link {target}")
            elif fragment and resolved.suffix == ".md":
                known = anchor_cache.setdefault(resolved, anchors(resolved))
                if fragment not in known:
                    out.append(f"{path.name}: missing anchor {target}")
    return out


def duplicate_problems(rows: list[Row]) -> list[str]:
    """Row IDs must be unique."""
    counts = Counter(row.row_id for row in rows)
    return [f"duplicate row ID {rid}" for rid, n in counts.items() if n > 1]


def summary(rows: list[Row], features: dict[str, Path]) -> str:
    """Markdown summary derived from the rows."""
    header = "| Category | Capabilities | Items | " + " | ".join(STATUSES) + " |"
    divider = "|---|---:|---:|" + "---:|" * len(STATUSES)
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
        cells = " | ".join(str(counts[s]) for s in STATUSES)
        lines.append(f"| {label} | {caps} | {len(mine)} | {cells} |")
    lines.append(
        f"| **Total** | **{total_caps}** | **{total_items}** | "
        + " | ".join(f"**{totals[s]}**" for s in STATUSES)
        + " |"
    )
    scope = Counter(r.scope for r in rows)
    pri = Counter(r.pri for r in rows)
    lines += [
        "",
        "| Scope | " + " | ".join(SCOPES) + " |",
        "|---|" + "---:|" * len(SCOPES),
        "| Items | " + " | ".join(str(scope[s]) for s in SCOPES) + " |",
        "",
        "| Priority | P0 | P1 | P2 | P3 |",
        "|---|---:|---:|---:|---:|",
        "| Items | " + " | ".join(str(pri[p]) for p in ("P0", "P1", "P2", "P3")) + " |",
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
    files = checklist_files()
    rows, features, problems = parse(files)
    for row in rows:
        problems += row_problems(row)
    problems += duplicate_problems(rows)
    problems += structure_problems(rows, features, files)
    problems += reference_problems(files, features, {row.row_id for row in rows})
    return rows, features, problems


def main(argv: list[str]) -> int:
    """Run the audit; return a process exit code."""
    rows, features, problems = audit()
    block = summary(rows, features)
    index_text = INDEX.read_text(encoding="utf-8")
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
