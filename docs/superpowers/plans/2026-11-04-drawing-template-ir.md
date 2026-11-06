# Drawing Template IR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `drawing_template` IR module: spec section 11.12, ADR-055, JSON Schema, fixtures and a pure validator, with no SOLIDWORKS generation.

**Architecture:** A new authored module beside Drawing Intent and Drawing Layout. `schemas/drawing-template/v0.json` holds the shape; `cad_ir.drawing_template` adds semantic rules and returns frozen dataclasses or an `IssueReport`, following `cad_ir.bundle.manifest`.

**Tech Stack:** Python 3 with pyright strict, `jsonschema` through `cad_ir.core.schema_validation`, JSON Schema 2020-12, pytest.

**Spec:** [docs/superpowers/specs/2026-11-04-drawing-template-ir-design.md](../specs/2026-11-04-drawing-template-ir-design.md)

## Global Constraints

- `cad-ir` is pure: no I/O, clock, network or CAD imports (G2). `lint-imports` enforces it.
- Schema rules from 3.4.8: `$id` is `https://sw-mcp.invalid/schemas/drawing-template/v0.json`; anchored portable patterns with no top-level `|`; `propertyNames`, never `patternProperties`; lengths by `$ref` to `../common/v0.json#/$defs/Length`.
- ID-keyed collections are JSON objects (3.4.1). Parsed collections are tuples sorted by key, each item carrying `key`.
- Generated files are never edited by hand: run `uv run python scripts/generate_contracts.py`.
- Semantic failures use `ErrorCode.IR_RULE_VIOLATED`. No new error codes.
- Do not open, move or change anything in `standards/iso/templates/` (ADR-022). `cad_drawing.checks` does not change.
- **Nothing is committed.** The branch has uncommitted milestone 5 work in some of the same files, and the owner has not asked for a commit. Tasks end with passing tests, not a commit.

## Review Focus

Each line has its test in Task 4.

- Margins larger than the paper: one error at `/border/margins`, with no cascade of "outside the border" errors and no crash.
- An inverted rectangle: one error for that rectangle, with no overlap or containment noise from it.
- A field box straddling two touching zones: rejected, because it must sit inside one zone. The two touching zones themselves pass.
- Edges that differ only within the length quantum (`230` and `230.0000004`): treated as touching, not overlapping or outside.
- A nearly empty template (`fields: {}`): all eight missing fields reported together, in deterministic order.

---

### Task 1: Specification, ADR and related documents

**Files:**
- Create: `docs/architecture/drawing-template-ir.md`, `docs/adr/ADR-055-generated-sheet-formats.md`
- Modify: `docs/architecture/overview.md`, `shared-ir-core.md`, `drawing-layout-ir.md`, `production-drawings.md`, `configuration.md`, `backend-operations.md`; `docs/specifications/README.md`, `roadmap.md`, `CHANGELOG.md`, `open-decisions.md`; `docs/development/repository-structure.md`; `docs/README.md`; `docs/adr/README.md`; every file whose header says `Specification v1.23`

**Interfaces:**
- Produces: the normative text the later tasks implement. Section 11.12 copies the design's module table, source grammar and the nine rules.

- [ ] **Step 1: Write `drawing-template-ir.md` (§11.12)**, in the shape of `drawing-layout-ir.md`: purpose, structure table, source grammar, example, validation rules, relation to Layout and D8, determinism. Mark the design's calls **[Builder's call]**. State that generation is not built and link K7.

- [ ] **Step 2: Write ADR-055** from `adr/template.md`, status Proposed. Decision: sheet formats may be generated from the IR, alongside owner-supplied `.slddrt` files. Alternative rejected: describing existing files only. It extends ADR-050 and does not withdraw it. Add its row to `adr/README.md`.

- [ ] **Step 3: Edit the shared documents.**
  - `overview.md`: add the module to the 3.1 diagram, 3.2 and the 3.3 diagram and tables. In the 3.3 rule 2 table: Drawing Template requires nothing and may reference nothing; Drawing Layout may reference Drawing Template. Add the late-bound source exception to rule 3.
  - `shared-ir-core.md`: module key in 3.4.1, the same exception in 3.4.2 rule 3, and in 3.4.5 several `drawing_template` documents allowed in a bundle.
  - `drawing-layout-ir.md`: `template` or `sheet_format` on a sheet, exactly one; a template sheet has no `size` or `orientation`; the `title_block` element and `tables` revision entry apply only to hand-made formats.
  - `production-drawings.md`: 11.2 title-block row allows generated formats; 11.5.3 D8 gets the derived-mapping rule, marked as not yet implemented.
  - `configuration.md` 13.3.4: mapping is for hand-made formats; a generated format has no TOML file.
  - `backend-operations.md` 6.5.2: new row, group `Sheet format`, operation `sheet_format.generate`, needed by `later`.

- [ ] **Step 4: Edit the registers and indexes.**
  - `open-decisions.md`: new item **K7** (generation path) with all topics from the design; the D8 consequence stated; blocks `later`; a note on K3; update the Summary's open-item count.
  - `specifications/README.md`: version `1.24`, section map row for 11.12.
  - `docs/README.md`: version, `ADR-001 … ADR-055`, new row in the IR modules table.
  - `roadmap.md`, `repository-structure.md` (`drawing-template/` under `schemas/`): add the module.
  - `CHANGELOG.md`: `## What changed in 1.24` at the top.

- [ ] **Step 5: Replace `Specification v1.23` with `v1.24` in every topic header.**

- [ ] **Step 6: Check nothing was missed.**

Run: `git grep -n "Specification v1.23" docs` (and the same search with `--untracked` if new files carry it)
Expected: no matches.

Run: `git grep -n "drawing_layout\|Drawing Layout IR" docs/api docs/architecture/drawing-intent-ir.md docs/specifications/product-spec.md docs/adr/ADR-046-document-ownership-and-outputs.md`
Expected: read each match; add the template only where the line lists all modules.

### Task 2: Module key and bundle rule

**Files:**
- Modify: `schemas/common/v0.json`, `packages/cad-ir/src/cad_ir/core/ids.py`, `packages/cad-ir/src/cad_ir/bundle/manifest.py`
- Modify (generated): `packages/cad-ir/src/cad_ir/generated/`
- Test: `packages/cad-ir/tests/test_ids.py`, `test_bundle_manifest.py`, `tests/fixtures/schemas/common/valid/{ModuleKey,DocumentRef,ItemRef}.json`

**Interfaces:**
- Produces: `"drawing_template"` in `ModuleKey` and `MODULE_KEYS` (last position).

- [ ] **Step 1: Write the failing tests.**
  - `test_ids.py`: extend the `MODULE_KEYS` assertion with `"drawing_template"`.
  - `test_bundle_manifest.py`:

```python
def test_several_drawing_templates_allowed() -> None:
    manifest = parse_bundle_manifest(
        _manifest("drawing_template:A3@1", "drawing_template:A3-CONT@1", "drawing_layout:d")
    )
    assert isinstance(manifest, BundleManifest)
    assert len(manifest.modules) == 3


def test_same_drawing_template_twice_rejected() -> None:
    report = parse_bundle_manifest(_manifest("drawing_template:A3@1", "drawing_template:A3@2"))
    assert isinstance(report, IssueReport)
    assert [i.pointer for i in report.issues] == ["/modules/1"]
```

  - Common fixtures: add `"drawing_template"`, `"drawing_template:ACME-A3@2"` and `"drawing_template:ACME-A3@2/main"` to the valid lists.

- [ ] **Step 2: Run them.**

Run: `uv run pytest packages/cad-ir/tests/test_ids.py packages/cad-ir/tests/test_bundle_manifest.py tests/contract/test_schema_fixtures.py -q`
Expected: the new cases FAIL.

- [ ] **Step 3: Implement.** Add the key to `ModuleKey`, `DocumentRef` and `ItemRef` in `common/v0.json`, and to `ids.py`. In `_semantic_issues`, exempt `drawing_template` from the one-per-key rule the same way as `part`, without the assembly condition. Update its docstring. Regenerate with `uv run python scripts/generate_contracts.py`.

- [ ] **Step 4: Run them again.** Same command. Expected: PASS, including existing tests. If a further test pins the module list, update it.

### Task 3: Schema and fixtures

**Files:**
- Create: `schemas/drawing-template/v0.json`, `tests/fixtures/schemas/drawing-template/valid/*.json`, `invalid/*.json`
- Modify: `tests/contract/test_schema_fixtures.py`; regenerate `cad_ir/generated/`

**Interfaces:**
- Consumes: `drawing_template` module key (Task 2).
- Produces: `https://sw-mcp.invalid/schemas/drawing-template/v0.json`, the document shape Task 4 parses.

The shape, with `additionalProperties: false` throughout:

| Path | Schema |
| --- | --- |
| root, required | `module` (const `drawing_template`), `schema_version` (`^0\.(0\|[1-9][0-9]*)$`), `units` (const `mm`), `paper`, `border`, `title_block`, `fields`. Also `id`, `revision`, `display_name` (string, min length 1), `texts`, `revision_table` |
| `paper` | `size` enum `A4 A3 A2 A1 A0`; `orientation` enum `portrait landscape` |
| `border` | `margins` with required `left right top bottom`, each `Length` with `exclusiveMinimum: 0`; optional `line_width`, positive |
| `$defs/Point`, `Rect` | As in the snapshot schema: `[x, y]` of `Length`; `{min, max}` |
| `title_block` | required `zones` (`minProperties: 1`, keys `ItemId`, values `Rect`); optional `lines` (keys `ItemId`; `from`, `to` required, `line_width` optional) |
| `$defs/TextPlacement` properties | `box` (`Rect`), `height` (positive), optional `align` enum `left center right` |
| `texts` | keys `ItemId`; `text` (string, min length 1) plus placement |
| `fields` | keys `ItemId`; `source` (array, `minItems: 1`, `uniqueItems: true`, ordered), optional `required` (boolean), optional `label` (string, min length 1), plus placement |
| `revision_table` | `box`, required |

Source pattern:

```
^(?:part_property:.+|drawing_property:.+|part_material|(?:design_intent|drawing_intent):[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*|sheet:(?:scale|projection|units))$
```

- [ ] **Step 1: Write the fixtures and tests.**
  - `valid/full.json`: A3 landscape with the eight minimum fields, a static text, a line and a revision table, passing all Task 4 rules too. `valid/minimal.json`: no `texts`, `lines`, `revision_table`, `id` or `revision`.
  - `invalid/` one file each: `wrong_module`, `units_inches`, `unknown_key`, `bad_paper_size`, `margin_zero`, `no_zones`, `zone_three_coords`, `bad_item_key`, `source_empty`, `source_unknown_kind`, `height_zero`.
  - `test_schema_fixtures.py`: add `TEMPLATE_ID`, `_template_cases(kind)` and `test_template_fixtures_exist_for_both_kinds`, `test_template_valid_accepted`, `test_template_invalid_rejected`, in the shape of the report tests.

- [ ] **Step 2: Run them.**

Run: `uv run pytest tests/contract/test_schema_fixtures.py -q -k template`
Expected: FAIL, because the schema does not exist.

- [ ] **Step 3: Write the schema, then regenerate** with `uv run python scripts/generate_contracts.py`.

- [ ] **Step 4: Run them again.** Same command, then all of `tests/contract/`. Expected: PASS.

### Task 4: Pure parser and semantic rules

**Files:**
- Create: `packages/cad-ir/src/cad_ir/drawing_template/__init__.py`, `model.py`, `rules.py`, `parse.py`
- Test: `packages/cad-ir/tests/test_drawing_template.py`

**Interfaces:**
- Consumes: schema (Task 3); `validate_against_schema`, `build_report`, `ValidationIssue`, `IssueReport`, `json_pointer`, `values_equal`, `ErrorCode`.
- Produces, exported from `cad_ir.drawing_template`:

```python
TEMPLATE_SCHEMA_ID: Final = "https://sw-mcp.invalid/schemas/drawing-template/v0.json"
MINIMUM_FIELDS: Final = (
    "part_number",
    "revision",
    "material",
    "finish",
    "general_tolerance",
    "scale",
    "projection_symbol",
    "units",
)
PAPER_SIZES_MM: Final  # A4 (210, 297), A3 (420, 297), A2 (594, 420), A1 (841, 594), A0 (1189, 841)


def parse_drawing_template(doc: JsonValue) -> DrawingTemplate | IssueReport: ...
```

Frozen, slotted dataclasses in `model.py`: `Rect(min_x, min_y, max_x, max_y)`, `Margins(left, right, top, bottom)`, `TitleBlockLine(key, start, end, line_width)`, `StaticText(key, text, box, height, align)`, `TemplateField(key, source, required, label, box, height, align)`, `DrawingTemplate(id, schema_version, display_name, paper_size, orientation, margins, border_line_width, zones, lines, texts, fields, revision_table_box)`. `zones` is `tuple[tuple[str, Rect], ...]`, sorted by key. Omitted optional values are `None`. `DrawingTemplate.sheet_size_mm` and `.border_rect` are properties. Text is NFC-normalized on input with `cad_ir.core.text` (3.4.3).

- [ ] **Step 1: Write the failing tests.** A `_valid_doc()` helper returns a fresh copy of `valid/full.json`'s content. Happy path: `test_valid_template_parses` checks `sheet_size_mm == (420, 297)`, `border_rect` from the margins, and keys sorted; `test_schema_failure_stops_before_rules`. `test_text_normalized_to_nfc`.

One parametrized `test_rule_violation(mutate, pointers)` asserts every issue is `IR_RULE_VIOLATED` and the pointer list is exact:

| Case | Mutation | Expected pointers |
| --- | --- | --- |
| `a4_landscape` | A4 landscape | `/paper/orientation` |
| `a3_portrait` | A3 portrait | `/paper/orientation` |
| `margins_too_big` | `left` = 500 | `/border/margins` only (Review Focus) |
| `inverted_zone` | zone `min` above `max` | that zone only (Review Focus) |
| `inverted_box` | field box inverted | `/fields/<name>/box` only |
| `zone_outside_border` | zone past the margin | that zone |
| `zones_overlap` | second overlapping zone | the later zone by key |
| `line_zero_length` | `from` equals `to` | that line |
| `line_outside_zone` | line leaves the zones | that line |
| `text_outside_border` | text box past the margin | `/texts/<key>/box` |
| `field_outside_zone` | field box above the block | `/fields/<name>/box` |
| `field_straddles_zones` | two touching zones, box across them | `/fields/<name>/box` only (Review Focus) |
| `revision_table_outside_zone` | box outside | `/revision_table/box` |
| `boxes_overlap` | text box over a field box | the later of the two by pointer |
| `text_taller_than_box` | `height` above box height | `/fields/<name>/height` |
| `minimum_field_missing` | delete `finish` | `/fields` |
| `all_fields_missing` | `fields: {}` | `/fields`, eight times (Review Focus) |
| `minimum_not_required` | `finish.required = false` | `/fields/finish/required` |
| `source_order` | `part_property:X` before `design_intent:y` | `/fields/<name>/source` |
| `sheet_source_not_alone` | `["sheet:scale", "part_property:X"]` | `/fields/scale/source` |

Plus these passing cases: `test_touching_zones_pass`; `test_edges_within_quantum_pass` (`230` and `230.0000004`, Review Focus); `test_explicit_required_true_passes`; `test_several_failures_all_reported`; `test_same_document_same_issue_order`.

- [ ] **Step 2: Run them.**

Run: `uv run pytest packages/cad-ir/tests/test_drawing_template.py -q`
Expected: FAIL on import.

- [ ] **Step 3: Implement `model.py`, `rules.py`, `parse.py`.** Order in `parse_drawing_template`: schema, build the model, run the rules, `build_report` if there are issues. `rules.py` exposes `semantic_issues(template: DrawingTemplate) -> list[ValidationIssue]`, made of one small function per rule. Two decisions the tests pin:
  - An inverted rectangle gets one issue, and is then left out of containment and overlap rules.
  - If rule 1 or rule 2 fails, every rule that needs the border is skipped for that document.

  Geometry goes through `_le(a, b)` (`a <= b or values_equal(a, b, "length")`) and overlap is true only when both axes overlap by more than the quantum. `MINIMUM_FIELDS` in `rules.py`. Source rank: `design_intent:` 0, `drawing_intent:` 1, the rest 2, non-decreasing.

- [ ] **Step 4: Run them again.** Same command. Expected: PASS.

### Task 5: Full verification and handoff

**Files:**
- Modify: `HANDOFF.md`, `docs/superpowers/specs/2026-11-04-drawing-template-ir-design.md` (status: approved)

- [ ] **Step 1: Run the Python suite and read each result.**

```bash
uv run python scripts/generate_contracts.py --check
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports
uv run pytest
```

Expected: every command exits 0. A failure that also exists without this work (milestone 5 in the tree) is reported, not hidden.

- [ ] **Step 2: Run the C# tests**, because `common/v0.json` changed.

Run: `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
Expected: all pass.

- [ ] **Step 3: Review the layering** with the `layering-reviewer` agent on `packages/cad-ir/`, and fix what it confirms.

- [ ] **Step 4: Update `HANDOFF.md`** (AGENTS.md section 5): spec v1.24, ADR-055, K7, the built module, what is unverified (nothing generated; no SOLIDWORKS), and next steps. Rewrite stale lines this work touches instead of appending. State the fresh test counts from Steps 1 and 2.
