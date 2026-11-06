# Drawing Report and Checks D5, D8, D10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Phase 1a checks that need no SOLIDWORKS: extend the snapshot, implement D5 (duplicates), D8 and D10, and produce a schema-valid drawing report in which D4, D6, D9 and D5's auxiliary marking are `not_evaluated`.

**Architecture:** Snapshot additions stay optional, so an absent field means "not read" and leads to `not_evaluated`, never to a guess. Each new check returns a `CheckOutcome` with status, reasons and rule failures. `report.py` combines those outcomes with the existing `GeometryCheckResult` into a `DrawingReport`.

**Tech Stack:** Python 3.13, `cad-ir`, pytest, pyright strict. No new dependencies.

**Spec:** `docs/architecture/production-drawings.md` §11.5, §11.5.1, §11.5.3, §11.5.4; `docs/architecture/configuration.md` §13.3.3–13.3.4; `docs/specifications/roadmap.md` §18 Phase 1a; ADR-042. Read §11.5.3 and §11.5.4 before starting: they fix every rule and code used below.

## Global Constraints

- The Global Constraints of `2026-11-03-shared-ir-core.md` and `2026-11-04-drawing-geometry-checks.md` apply: purity (G2, no I/O or clock in `cad_drawing`), frozen dataclasses, pyright strict, ruff, §3.4.8 schema rules, generated files only via `scripts/generate_contracts.py`.
- Code: `packages/cad-drawing/src/cad_drawing/checks/`. Tests: `packages/cad-drawing/tests/`, contract tests in `tests/contract/test_schema_fixtures.py`.
- Keep functions under 50 lines and files under 400. Do not change the behaviour of D1, D2, D3, D7 or `run_geometry_checks`.
- No SOLIDWORKS, no live tests, no code from the reference implementation. Do not invent title-block field locations (register K3); the mapping is an input.
- **Do not run git commit or git add.** The controller commits after review.
- Full suite after every task, from the repo root: `uv run python scripts/generate_contracts.py --check && uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest -q`.

## Review Focus

1. **A half-run check never reads as pass.** D5 with clean duplicates and no intent is `not_evaluated`, with `parts.duplicates == "pass"`. Test: `test_d5_clean_is_not_evaluated_without_intent`.
2. **Absent is not empty.** `parameters: []` is a reference dimension and counts as read; a missing `parameters` is unread. A `""` title field is unfilled (failure); a sheet without `title_block_fields` is `not_evaluated`. Tests: `test_d5_empty_parameters_is_read`, `test_d5_missing_data_not_evaluated`, `test_d8_absent_fields_not_evaluated`.
3. **Parallel directions across the wrap.** Dimension lines drawn left-to-right and right-to-left, or at 0° and 179.9999°, fall in one bin. A horizontal and a vertical dimension between the same two entities are not a chain. Tests: `test_d5_chain_reversed_direction`, `test_d5_chain_wrap_at_180`, `test_d5_horizontal_and_vertical_same_entities_ok`.
4. **The report cannot say done.** Even a clean snapshot with every field present gives verdict `not_evaluated`, and `calibration.status` is `unverified`. Test: `test_clean_full_snapshot_is_not_done`.
5. **Same inputs, same bytes.** Reversed key order in the snapshot gives identical canonical report bytes. Test: `test_report_deterministic_under_key_order`.

---

### Task 1: Snapshot additions

**Files:**
- Modify: `schemas/drawing-geometry-snapshot/v0.json`, `checks/snapshot.py`, `checks/thresholds.py`
- Regenerate: `uv run python scripts/generate_contracts.py`
- Create fixtures in `tests/fixtures/schemas/drawing-geometry-snapshot/`: `valid/checks_data.json` (copy of `two_dimensions` with every new field, clean: both dimensions with `parameters` and `parenthesized: false`, all 8 minimum fields filled, `sheet_format` `"Test-A3.slddrt"`, revision table ending in the revision field, `rebuild` completed, no errors, `reopen: "verified"`); `invalid/bad_reopen.json`, `invalid/bad_rebuild_error_kind.json`, `invalid/rebuild_missing_reopen.json`, `invalid/parameters_not_strings.json`, `invalid/parameters_duplicate.json`, `invalid/title_field_not_string.json`
- Test: `packages/cad-drawing/tests/test_snapshot.py`; the contract harness picks fixtures up by directory.

**Interfaces (Produces), in `snapshot.py`:**
- `type RebuildErrorKind = Literal["dangling", "annotation_error", "rebuild_error"]`, `type ReopenState = Literal["verified", "failed", "not_checked"]`
- `RevisionTable(entries: tuple[str, ...])`
- `RebuildError(kind: RebuildErrorKind, sheet: str | None, annotation: str | None, message: str)`
- `AnnotationRef(sheet: str, annotation: str)`
- `Rebuild(completed: bool, errors: tuple[RebuildError, ...], silhouette_attachments: tuple[AnnotationRef, ...], reopen: ReopenState)`
- Added, last and defaulted so existing constructors still work:
  - `Annotation.parameters: tuple[str, ...] | None = None` (sorted when parsed), `Annotation.parenthesized: bool | None = None`
  - `Sheet.sheet_format: str | None = None`, `Sheet.title_block_fields: tuple[tuple[str, str], ...] | None = None` (sorted by name; a tuple keeps the dataclass hashable and immutable), `Sheet.revision_table: RevisionTable | None = None`
  - `Snapshot.rebuild: Rebuild | None = None`
- `CheckThresholds.parallel_deg: float = 0.01`, included in `to_json()`.

**Schema:** as §11.5.1. `Annotation.parameters`: array of strings (`minLength` 1), `x-unordered`, `uniqueItems`. `Sheet.title_block_fields`: object with `propertyNames` ItemId and string values. `Sheet.revision_table`: `{entries: array of string}` or null. `Sheet.sheet_format`: string or null. Root `rebuild`: `completed`, `errors`, `silhouette_attachments`, `reopen` all required; `sheet` and `annotation` are ItemId or null on errors, ItemId on silhouette entries; `silhouette_attachments` is `x-unordered`.

- [ ] **Step 1: Failing tests** in `test_snapshot.py`:
  - `test_parse_new_fields`: `checks_data.json` parses, values as written, title fields sorted
  - `test_new_fields_default_to_none`: `two_dimensions.json` gives `None` for all of them
  - `test_rebuild_unknown_sheet_is_rule_issue` and `test_rebuild_unknown_annotation_is_rule_issue`: errors and silhouette entries naming no item return an `IssueReport` with `IR_RULE_VIOLATED` and the pointer of the entry (`/rebuild/errors/0/annotation`, `/rebuild/silhouette_attachments/0/sheet`)
  - `test_rebuild_annotation_needs_sheet`: an error with an `annotation` and null `sheet` is also `IR_RULE_VIOLATED`
  - `test_thresholds_parallel_deg`: default 0.01, present in `to_json()`
- [ ] **Step 2:** Add the fixtures. Run `uv run pytest tests/contract packages/cad-drawing/tests/test_snapshot.py -q`. Expected: FAIL.
- [ ] **Step 3:** Update the schema, run the generator, implement parsing and the rule issues (extend the existing rule-issue pass in `parse_snapshot`).
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 2: Rule outcomes and D5

**Files:** Create `checks/outcome.py`, `checks/d5.py`. Test: `test_outcome.py`, `test_d5.py`. In `tests/conftest.py`, give the `Builder.annotation` method keyword arguments `parameters`, `parenthesized` and `view`, with defaults that keep existing tests unchanged.

**Interfaces (Produces), in `outcome.py`:**
- `type CheckStatus = Literal["pass", "fail", "not_evaluated"]`
- `type ReasonCode = Literal["drawing_intent_required", "dimension_data_missing", "title_block_mapping_missing", "title_block_data_missing", "rebuild_data_missing", "reopen_not_checked"]`
- `RuleItem(kind: Literal["annotation", "title_field"], id: str, sheet: str | None)`, `to_json()` omitting nothing
- `RuleFailure(check: Literal["D5", "D8", "D10"], sheet: str | None, code: str, items: tuple[RuleItem, ...], detail: tuple[tuple[str, str], ...], message: str)`, with `to_json()` (`detail` as an object) and `sort_key(sheet_index: Mapping[str, int])`: `(index or -1 for null sheet, check number, item keys, code, detail)`
- `CheckWarning(code: str, sheet: str, annotation: str, message: str)`, `to_json()`
- `CheckOutcome(status: CheckStatus, failures: tuple[RuleFailure, ...] = (), reasons: tuple[ReasonCode, ...] = (), warnings: tuple[CheckWarning, ...] = (), parts: tuple[tuple[str, CheckStatus], ...] = ())`
- `combine_status(statuses: Iterable[CheckStatus]) -> CheckStatus`: `fail`, then `not_evaluated`, then `pass`; an empty input is `pass`

**In `d5.py`:** `check_d5(snapshot: Snapshot, t: CheckThresholds) -> CheckOutcome`, by §11.5.3. Parts are `(("auxiliary_marking", "not_evaluated"), ("duplicates", <status>))`. `reasons` always holds `drawing_intent_required`, and `dimension_data_missing` only when the duplicates part is `not_evaluated`.

Direction bin, so 0° and 179.9999° agree:

```python
bins = round(180.0 / t.parallel_deg)
bin_index = round(math.degrees(math.atan2(dy, dx)) % 180.0 / t.parallel_deg) % bins
```

Graph: for each sheet, group candidates by `(view, bin_index)`. Take dimensions in key order. If the two entities are already connected in that group's forest, the failure's items are that dimension plus the path between them (found by BFS); the dimension is then not added to the forest. Otherwise add it. Direction comes from the first non-zero segment of the first polyline; a candidate needs at least one dimension line, all of them polylines, and a non-zero segment. `detail`: `(("parameter", name),)` for a duplicate, `()` for a chain. A duplicate's `sheet` is the single sheet involved, or null across sheets; a chain's `sheet` is its sheet.

- [ ] **Step 1: Failing tests:**
  - `test_combine_status_order`
  - `test_d5_duplicate_parameter`: two dimensions share `"D1@Sketch1"` on one sheet: one failure, code `duplicate_parameter`, status `fail`, parts duplicates `fail`
  - `test_d5_duplicate_across_sheets`: sheet is null, items carry each sheet
  - `test_d5_parenthesized_duplicate_still_fails`
  - `test_d5_empty_parameters_is_read`: reference dimensions with `[]` never collide and give no `dimension_data_missing`
  - `test_d5_clean_is_not_evaluated_without_intent`: status `not_evaluated`, duplicates `pass`, reasons `("drawing_intent_required",)`
  - `test_d5_missing_data_not_evaluated`: a dimension with no `parameters` adds `dimension_data_missing`; a note without them does not; missing data plus a real duplicate is `fail`
  - `test_d5_closed_chain`: a–b, b–c, a–c horizontal in one view: one failure naming all three, code `closed_chain`
  - `test_d5_chain_with_parenthesized_is_open`
  - `test_d5_two_parallel_same_entities`: shortest cycle
  - `test_d5_open_chain_ok`: a–b, b–c only
  - `test_d5_chain_reversed_direction`, `test_d5_chain_wrap_at_180`
  - `test_d5_horizontal_and_vertical_same_entities_ok`
  - `test_d5_chain_separate_views_ok`
  - `test_d5_unknown_parenthesized_stays_out_of_graph`: such a dimension cannot close a chain, and the part is `not_evaluated`
  - `test_d5_arc_and_ordinate_skipped`: an arc dimension line, and a dimension with one extension line, are not candidates
  - `test_d5_two_cycles_deterministic`: a graph with two cycles gives the same failures under any input order
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 3: D8 and D10

**Files:** Create `checks/d8.py`, `checks/d10.py`. Test: `test_d8.py`, `test_d10.py`.

**Interfaces (Produces):**
- `d8.py`:
  - `MINIMUM_TITLE_FIELDS: tuple[str, ...] = ("part_number", "revision", "material", "finish", "general_tolerance", "scale", "projection_symbol", "units")`
  - `TitleBlockMapping(template: str, required: tuple[str, ...] = (), revision_table: bool = False)`
  - `check_d8(snapshot: Snapshot, mappings: Mapping[str, TitleBlockMapping]) -> CheckOutcome`
- `d10.py`: `check_d10(snapshot: Snapshot) -> CheckOutcome`

Rules and codes: §11.5.3. D8 details: a field failure has item `RuleItem("title_field", name, sheet)`, `detail ()`; a mismatch has `detail (("latest_entry", x), ("revision", y))` and item `revision`. Skip the mismatch when `revision` is already unfilled. The `$PRP` test is on the upper-cased text. Compare with `unicodedata.normalize("NFC", s.strip())`. Mapping lookup comes first, then `title_block_fields`. With no sheets, D8 is `not_evaluated` with `title_block_data_missing`.

D10 details: an error failure has one annotation item when it names one; `message` copies the error's message; `sheet` copies the error's sheet. `rebuild_not_completed` and `reopen_failed` have a null sheet and no items. Warnings use code `silhouette_attachment`, in `(sheet, annotation)` order. `not_checked` adds reason `reopen_not_checked`; with failures, the status is still `fail` and that reason stays.

- [ ] **Step 1: Failing tests:**
  - `test_d8_all_filled_passes`
  - `test_d8_empty_and_whitespace_fail`, `test_d8_absent_field_fails` (a required name not in the object), one failure per field with code `title_field_unfilled`
  - `test_d8_unresolved_link_fails`: `$PRPSHEET:"PartNo"`
  - `test_d8_minimum_applies_even_if_mapping_omits`, `test_d8_mapping_adds_required`
  - `test_d8_no_mapping_not_evaluated`: reason `title_block_mapping_missing`; also for a null `sheet_format`
  - `test_d8_absent_fields_not_evaluated`: reason `title_block_data_missing`
  - `test_d8_no_sheets_not_evaluated`
  - `test_d8_fail_on_one_sheet_wins_over_unmapped_other`: status `fail`, reason retained
  - `test_d8_revision_table_latest_matches`: last entry counts, surrounding whitespace ignored
  - `test_d8_revision_table_mismatch`, `test_d8_case_differs_is_mismatch`
  - `test_d8_revision_table_required_but_null`, `test_d8_revision_table_no_entries`: code `revision_table_missing`
  - `test_d8_table_present_though_not_required_is_checked`
  - `test_d8_unfilled_revision_gives_no_mismatch`
  - `test_d10_missing_section_not_evaluated`: reason `rebuild_data_missing`
  - `test_d10_clean_passes`
  - `test_d10_error_kinds`: one failure per error, code from kind, sheet and item copied
  - `test_d10_not_completed_fails`, `test_d10_reopen_failed_fails`
  - `test_d10_not_checked_not_evaluated`, `test_d10_not_checked_with_error_is_fail`
  - `test_d10_silhouette_is_warning_only`: status `pass`, one warning
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 4: Drawing report and schema

**Files:**
- Create: `schemas/drawing-report/v0.json` (delete its `.gitkeep`); `checks/report.py`; `tests/fixtures/schemas/drawing-report/valid/checks_data.json` (golden output of `build_report` on the snapshot fixture `checks_data.json` with mapping `Test-A3.slddrt` and `revision_table=True`); invalid fixtures `calibrated_status.json` (`calibration.status` `"calibrated"`), `missing_check.json` (no D9), `bad_verdict.json`, `missing_calibration.json`, `rule_failure_no_code.json`
- Modify: `checks/__init__.py` (export `build_report`, `DrawingReport`, `TitleBlockMapping`, `CheckOutcome`, `RuleFailure`, `REPORT_SCHEMA_ID`), `tests/contract/test_schema_fixtures.py` (a `REPORT_ID` and valid/invalid cases like the snapshot ones)
- Regenerate: `uv run python scripts/generate_contracts.py`
- Test: `packages/cad-drawing/tests/test_report.py`

**Interfaces (Produces), in `report.py`:**
- `REPORT_SCHEMA_ID = "https://sw-mcp.invalid/schemas/drawing-report/v0.json"`, `REPORT_SCHEMA_VERSION = "0.1"`
- `CALIBRATION_NOTE = "Checks have run only on synthetic snapshots; results are unverified on real SOLIDWORKS data."`
- `ALL_CHECKS: tuple[str, ...]`: `D1` to `D10` in order
- `compute_verdict(statuses: Mapping[str, CheckStatus]) -> Literal["done", "fail", "not_evaluated"]`: `fail` if any `fail`; `done` only if every one of `ALL_CHECKS` is present and `pass`; otherwise `not_evaluated`
- `DrawingReport(snapshot_hash: str, snapshot: Snapshot, geometry: GeometryCheckResult, outcomes: Mapping[str, CheckOutcome])`: frozen, with `status(check) -> CheckStatus`, `verdict` property, `to_json() -> JsonValue`
- `build_report(doc: JsonValue, *, thresholds: CheckThresholds | None = None, title_block_mappings: Mapping[str, TitleBlockMapping] | None = None) -> DrawingReport | IssueReport`: parses `doc` (returning the issues if invalid), runs the geometry checks, D5, D8, D10, and sets D4, D6, D9 to `CheckOutcome("not_evaluated", reasons=("drawing_intent_required",))`. The hash is `content_hash(doc)`.

**JSON shape:** §11.5.4. `drawing`: `{document, revision}`. `solidworks`: `{version, service_pack}`. `snapshot`: `{hash, schema_version, captured_at}`. `checks.<id>`: `{status, failure_count, reasons}` plus `parts` on D5 as an object. `failures`: geometric failures, then rule failures, merged and stably sorted on `(sheet index or -1, check number)`, so each check keeps its own order. `warnings` as in Task 3. `sheets.<key>`: `{index, soft_metrics, text_extents: {display_data, font_metrics}}`. `thresholds`: `CheckThresholds.to_json()`. `conflict_count`: `len(failures)`.

**Schema:** root and objects open (derived artifact, ADR-042), every field above required. `calibration.status` is `{"const": "unverified"}`. `verdict`, check `status` and `reasons` are enums. `checks` requires all of D1–D10. A `failures` item is a `oneOf`: geometric requires `distance_mm`, `threshold_mm`, `location`, `methods`, and forbids `code` with `"not": {"required": ["code"]}`; rule requires `code`, `detail`, `message`, and forbids `distance_mm` the same way. `hash` is `ContentHash`; numbers use `Length`/`Count` by `$ref` as in the snapshot. `sheet` is ItemId or null.

- [ ] **Step 1: Failing tests:**
  - `test_compute_verdict`: all pass gives `done`; one `not_evaluated` gives `not_evaluated`; one `fail` with some `not_evaluated` gives `fail`; a missing check is never `done`
  - `test_clean_full_snapshot_is_not_done`: `checks_data.json` with its mapping: D1, D2, D3, D7, D8, D10 `pass`; D4, D5, D6, D9 `not_evaluated`; verdict `not_evaluated`; `calibration == {"status": "unverified", "note": CALIBRATION_NOTE}`
  - `test_old_snapshot_all_new_checks_not_evaluated`: `two_dimensions.json` without mapping: D8, D10 `not_evaluated`, D5 reasons include `dimension_data_missing`
  - `test_seeded_defects_fail_verdict`: a duplicate, a dangling dimension, an empty title field and a D2 overlap: verdict `fail`, `conflict_count` 4, failures in sheet then check order
  - `test_document_level_failures_come_first`: `reopen_failed` (null sheet) sorts before sheet failures
  - `test_report_output_matches_schema`: `validate_against_schema(report.to_json(), REPORT_SCHEMA_ID) == ()` for every valid snapshot fixture, with and without mappings, and for the seeded-defect report
  - `test_golden_report_fixture`: `to_json()` equals the fixture
  - `test_report_deterministic_under_key_order`: reversed-key input gives equal `canonical_bytes(report.to_json())`, including `snapshot.hash`, because RFC 8785 sorts keys
  - `test_invalid_snapshot_returns_issue_report`
  - `test_text_extents_counted`: one box of each method
  - `test_thresholds_recorded`
  - `test_report_does_not_mutate_input`: deep copy before, equal after
- [ ] **Step 2:** Add fixtures and tests. Run. Expected: FAIL.
- [ ] **Step 3:** Write the schema and run the generator; implement `report.py`; generate the golden fixture from the implementation, then read it and confirm it matches the spec by hand before accepting it.
- [ ] **Step 4:** Run the full suite plus `uv run pytest --cov=packages/cad-drawing/src --cov-report=term -q packages/cad-drawing`. Expected: PASS, with `cad_drawing.checks` coverage ≥ 80%.

## Out of scope (next milestone)

- D4, D6, D9, and D5's auxiliary marking on a Drawing Intent (Phase 1b).
- `check_drawing` / `get_drawing_report` tools, the store, IPC, and the add-in producing these snapshot fields (A15, A16).
- The title-block mapping's TOML parsing and read-back locators (K3).
- Reporting a draft-to-high-quality view switch (8.4), and ADR-045's service-pack warning: both are `warnings` codes added with the read-back.
- Dimension spacing uniformity (a soft metric not yet built).
