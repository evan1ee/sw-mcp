# Drawing Geometry Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the Drawing Geometry Snapshot schema and implement the pure checks D1, D2, D3, D7 and the geometric soft metrics, so Phase 1a checks run offline on recorded snapshots.

**Architecture:** `schemas/drawing-geometry-snapshot/v0.json` is the contract (§11.5.1 Encoding). In `cad-drawing/checks/`:
- `geometry2d.py`: exact 2D primitives and distances.
- `snapshot.py`: parses a validated snapshot into frozen dataclasses.
- `primitives.py`: builds the §11.5.2 check primitives (tessellated arcs, text boxes enlarged by the font-metric margin).
- `spatial.py`: a uniform-grid index that keeps pair tests near-linear.
- `d1.py`, `d2.py`, `d3.py`, `d7.py`, `soft_metrics.py`: one check each.
- `runner.py`: runs the checks in a fixed order.

Everything is pure (G2): no I/O and no SOLIDWORKS.

**Tech Stack:** Python 3.13, `cad-ir` (schema validation, issues, canonical hashing), pytest, pyright strict. No new dependencies; geometry is hand-written, because the shapes are only segments, polylines and convex quadrilaterals.

**Spec:** `docs/architecture/production-drawings.md` §11.5, §11.5.1 (including Encoding), §11.5.2; `docs/architecture/configuration.md` §13.3.3 `drawing.check.*`; `docs/architecture/shared-ir-core.md` §3.4; ADR-031, ADR-042.

## Global Constraints

- Everything in the Global Constraints of `2026-11-03-shared-ir-core.md` applies: purity, immutability, pyright strict, ruff, `fullmatch`, schema rules of §3.4.8, generated files only via `scripts/generate_contracts.py`.
- Code lives in `packages/cad-drawing/src/cad_drawing/checks/`; unit tests in `packages/cad-drawing/tests/`. `cad_drawing` may import `cad_ir` only (not `cad_protocol`, `cad_application`; `lint-imports` enforces).
- Thresholds, defaults from §13.3.3:
  - `epsilon_mm = 0.01`
  - `text_clearance_mm = 0.5`
  - `line_clearance_mm = 0.25`
  - `edge_clearance_mm = 0.25`
  - `font_metric_margin = 0.1`
  - arc chord error ≤ 0.02 mm
- Lengths are sheet millimetres as floats; geometry functions never round. Only reported numbers (`distance_mm`, `location`) are quantized with `cad_ir.core.quantize(..., "length")`.
- The snapshot is a derived artifact: the schema does **not** set `additionalProperties: false`; unknown fields are ignored (ADR-042).
- Full suite after every task: `uv run python scripts/generate_contracts.py --check && uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest -q`.

## Review Focus

1. **Degenerate geometry.** Zero-length segments, a polyline with one repeated point, text boxes with zero area, and arcs with `start_deg == end_deg` must not divide by zero or raise; distances stay correct. Tests: Task 2 `test_degenerate_segments`, Task 3 `test_degenerate_arc_and_box`.
2. **Touching counts as crossing.** Two segments that meet exactly at an endpoint, or come within ε, are D1 failures; parallel collinear overlap is a failure too. Tests: Task 4 `test_d1_touching_and_collinear`.
3. **Floating-point near-misses.** A gap of `threshold - 1e-9` fails and `threshold + 1e-9` passes. Comparisons are `distance < threshold` for clearances and `distance <= epsilon` for crossings, exactly as written in Tasks 4–5. Tests: `test_d2_threshold_boundary`, `test_d1_epsilon_boundary`.
4. **Rotated and arc-only annotations.** Text boxes at arbitrary angles and angular dimensions whose lines are arcs must be checked like axis-aligned ones. Tests: Task 5 `test_d2_rotated_boxes`, Task 4 `test_d1_arc_dimension`.
5. **Order and determinism.** The same snapshot with keys inserted in a different order must give an identical failure list and identical `content_hash`. Test: Task 6 `test_runner_deterministic_under_key_order`.

---

### Task 1: Snapshot schema and fixtures

**Files:**
- Create: `schemas/drawing-geometry-snapshot/v0.json` (delete its `.gitkeep`); `tests/fixtures/schemas/drawing-geometry-snapshot/{valid,invalid}/*.json`
- Regenerate: `uv run python scripts/generate_contracts.py`
- Test: the existing harness `tests/contract/test_schema_fixtures.py` must pick the new directory up. If it is keyed per schema directory, add a parametrize entry mapping `drawing-geometry-snapshot` → `https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json`.

**Interfaces:**
- Produces the schema `$id` `https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json` with these `$defs`. References into common use `../common/v0.json#/$defs/...`; numbers in mm use `Length`.
  - Geometry:
    - `Point`: array of exactly 2 `Length`
    - `Polyline`: array of ≥ 2 `Point`
    - `Arc`: `{center: Point, radius: Length (exclusiveMinimum 0), start_deg: Angle, end_deg: Angle}`, counter-clockwise
    - `Curve`: `oneOf [{polyline: Polyline}, {arc: Arc}]`, each branch closed with `additionalProperties: false`, so the two branches are exclusive
    - `Rect`: `{min: Point, max: Point}`
  - `TextBox`: `{corners: array of exactly 4 Point, height_mm: Length (minimum 0), method: enum display_data|font_metrics, text: string}`
  - `ExtensionLine`: `{line: Polyline, entity: string}`
  - `Arrowhead`: `{polygon: array ≥ 3 Point}`
  - `Annotation`:
    - required: `kind` (enum `dimension`, `callout`, `note`, `gdt`, `datum`, `surface_finish`, `center_mark`, `centerline`, `balloon`), `native_id` (string)
    - optional: `tag` (ItemId or null), `view` (ItemId or null; null means the annotation sits on the sheet), `attachments` (array of string, `x-unordered`)
    - optional geometry: `dimension_lines` (array of Curve), `extension_lines` (array of ExtensionLine), `arrowheads` (array of Arrowhead), `leaders` (array of Polyline), `text_boxes` (array of TextBox)
  - `Edge`: `{curve: Curve, kind: enum visible|silhouette|hidden|centerline|center_mark}`
  - `View`: `{native_id, scale: Ratio, outline: Rect, edges: array of Edge}`
  - `Sheet`: `{index: Count, native_id, size_mm: Point, border: Rect, title_block: array of Rect, views: object (propertyNames ItemId, values View), annotations: object (propertyNames ItemId, values Annotation)}`
- Root, all fields required except `drawing.revision`:
  - `schema_version` (SchemaVersion, `0.x`)
  - `drawing`: `{document: string, revision: Revision | null}`
  - `solidworks`: `{version: string, service_pack: string}`
  - `captured_at`: string, `format: date-time`
  - `sheets`: object (propertyNames ItemId, values Sheet)
- Fixtures:
  - valid:
    - `minimal.json`: one sheet, no views
    - `two_dimensions.json`: one view, a box edge outline, two linear dimensions with text boxes and extension lines
    - `angular_arc.json`: an angular dimension whose dimension line is an `arc`
  - invalid:
    - `curve_both.json`: a Curve with both `polyline` and `arc`
    - `point_three_coords.json`
    - `textbox_three_corners.json`
    - `bad_sheet_key.json`: key `Sheet1`
    - `nan_coordinate.json`: written as a Python test case, because JSON cannot hold NaN. Add `test_snapshot_rejects_nan` to `test_schema_fixtures.py`, using `validate_against_schema`.
    - `missing_sheets.json`

- [ ] **Step 1:** Write the fixtures and the NaN test. Run `uv run pytest tests/contract -q`. Expected: FAIL (unknown schema).
- [ ] **Step 2:** Write the schema and run the generator.
- [ ] **Step 3:** Run `uv run pytest tests/contract -q`, then the full suite. Expected: PASS.

### Task 2: 2D geometry primitives

**Files:** Create `packages/cad-drawing/src/cad_drawing/checks/geometry2d.py`. Test: `packages/cad-drawing/tests/test_geometry2d.py`.

**Interfaces (Produces):**
- `type Vec = tuple[float, float]`
- `Segment(a: Vec, b: Vec)` (frozen)
- `Quad(corners: tuple[Vec, Vec, Vec, Vec])`, a convex quadrilateral; vertex order may be clockwise or counter-clockwise
- `point_segment_distance(p: Vec, s: Segment) -> float`
- `segment_distance(s: Segment, t: Segment) -> float`: 0 when they intersect, including collinear overlap and endpoint touching
- `segment_quad_distance(s: Segment, q: Quad) -> float`: 0 when the segment touches or enters the quad
- `quad_distance(q: Quad, r: Quad) -> float`: 0 when they overlap or one contains the other
- `polygon_segments(points: Sequence[Vec], closed: bool) -> tuple[Segment, ...]`: drops zero-length segments
- `tessellate_arc(center: Vec, radius: float, start_deg: float, end_deg: float, max_chord_error: float = 0.02) -> tuple[Vec, ...]`
  - counter-clockwise from start to end
  - a sweep of `(end - start) mod 360`, where an equal start and end means a sweep of 0 and returns a single point
  - number of steps `n = max(1, ceil(sweep_rad / (2 * acos(1 - e / r))))`, where `e / r` is clamped to `≤ 1`
  - returns `n + 1` points including both ends
- `inflate_quad(q: Quad, d: float) -> Quad`: moves each side outward by `d` along its normal; for a rectangle, that means each half-extent grows by `d`
- `aabb(points: Iterable[Vec]) -> tuple[float, float, float, float]`

Approach: `segment_distance` uses an orientation-based proper/collinear intersection test, then the minimum of the four point–segment distances. The quad functions return 0 if any segment intersects or a vertex lies inside (sign of cross products); otherwise they return the minimum segment–segment distance over the edges.

- [ ] **Step 1: Failing tests:**
  - `test_crossing_segments_zero`: (0,0)-(2,2) × (0,2)-(2,0) → 0
  - `test_parallel_distance`: (0,0)-(10,0) vs (0,1)-(10,1) → 1.0
  - `test_endpoint_touch_zero`
  - `test_collinear_overlap_zero`
  - `test_collinear_gap`: (0,0)-(1,0) vs (3,0)-(4,0) → 2.0
  - `test_degenerate_segments`: a zero-length segment behaves like a point
  - `test_quad_contains_quad_zero`
  - `test_rotated_quad_distance`: a unit square rotated 45° centred at (0,0), against a segment at x = 2 → `2 - sqrt(2)/2`
  - `test_tessellate_quarter_circle`: r = 10, 0→90: every chord midpoint is within 0.02 of the circle; first point (10, 0), last (0, 10)
  - `test_tessellate_wraps`: 350→10 sweeps 20°
  - `test_inflate_quad`
  - Use `pytest.approx(abs=1e-12)`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 3: Snapshot model and check primitives

**Files:** Create `checks/snapshot.py`, `checks/primitives.py`, `checks/thresholds.py`. Test: `test_snapshot.py`, `test_primitives.py`.

**Interfaces:**
- Consumes: `validate_against_schema`, `build_report`, `IssueReport`, `JsonValue` (cad_ir.core); Task 2.
- `SNAPSHOT_SCHEMA_ID = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"`
- `CheckThresholds(epsilon_mm=0.01, text_clearance_mm=0.5, line_clearance_mm=0.25, edge_clearance_mm=0.25, font_metric_margin=0.1, arc_chord_error_mm=0.02)`: frozen, and `to_json()` returns the keys as named in §13.3.3 without the `drawing.check.` prefix
- `snapshot.py` frozen dataclasses mirroring Task 1:
  - `Snapshot(sheets: tuple[Sheet, ...] sorted by index, ...)`
  - `Sheet(key, index, size_mm, border, title_block, views: tuple[View, ...] sorted by key, annotations: tuple[Annotation, ...] sorted by key)`
  - curves become `PolylineCurve(points)` / `ArcCurve(center, radius, start_deg, end_deg)`
  - `parse_snapshot(doc: JsonValue) -> Snapshot | IssueReport`: validates against the schema first and returns the report if there are any issues
- `primitives.py`:
  - `type PrimKind = Literal["dimension_line", "extension_line", "arrowhead", "text_box", "edge"]`
  - `Prim(kind: PrimKind, owner: str, segments: tuple[Segment, ...], quad: Quad | None, method: str | None, entity: str | None, index: int)`
    - `owner` is the annotation key for annotation prims and the view key for edges.
    - `index` is the position in its source list, and for edges it is the edge index.
    - `entity` is set only for extension lines.
    - `quad` is set only for text boxes and arrowheads. An arrowhead becomes a quad when it has 4 points; otherwise it is represented only by its outline segments.
  - `sheet_primitives(sheet: Sheet, t: CheckThresholds) -> tuple[Prim, ...]`
    - Leaders count as `dimension_line` (§11.5.2).
    - Arcs are tessellated with `t.arc_chord_error_mm`.
    - A `font_metrics` text box is inflated by `t.font_metric_margin * height_mm`.
    - Edges of every kind are included (hidden edges appear only if the view displays them, per §11.5.1).
    - The output order is deterministic (by owner, kind, index).

- [ ] **Step 1: Failing tests:**
  - `test_parse_valid_fixture` (loads `two_dimensions.json` in the test; the test may do I/O): 1 sheet, 2 annotations, sorted
  - `test_parse_invalid_returns_report`: `IR_SCHEMA_INVALID`
  - `test_font_metric_box_inflated`: a 10×2 box, height 2, margin 0.1 → each side moves by 0.2
  - `test_display_data_box_not_inflated`
  - `test_leader_is_dimension_line`
  - `test_arc_dimension_tessellated`
  - `test_degenerate_arc_and_box`: start == end gives no segments and no error; a zero-area box still yields a quad
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 4: Spatial index, failure record and D1

**Files:** Create `checks/spatial.py`, `checks/failures.py`, `checks/d1.py`. Test: `test_spatial.py`, `test_d1.py`.

**Interfaces:**
- `GridIndex.build(prims: Sequence[Prim], cell_mm: float = 10.0)` with `candidate_pairs(a: Sequence[Prim], b: Sequence[Prim] | None, pad: float) -> Iterator[tuple[Prim, Prim]]`
  - Yields each unordered pair whose AABBs, padded by `pad`, share a cell, exactly once.
  - Pairs come in a deterministic order.
  - With `b=None` it pairs within `a`.
- `CheckItem(kind: Literal["annotation", "edge", "view"], id: str, index: int | None = None)`
- `CheckFailure(check: Literal["D1", "D2", "D3", "D7"], sheet: str, items: tuple[CheckItem, CheckItem] | tuple[CheckItem], distance_mm: float, threshold_mm: float, location: Vec, methods: tuple[str | None, ...])`
  - `items` are sorted.
  - `distance_mm` and `location` are quantized.
  - `location` is the midpoint of the closest points. A helper `closest_points(s, t) -> tuple[Vec, Vec]` in `geometry2d` may be added for this.
  - `to_json()`
- `sort_failures(fs) -> tuple[CheckFailure, ...]`: orders by (sheet index, check, items), per §11.5.2 Reporting. The sheet index comes from the snapshot, so it is passed in as a mapping key → index.
- `check_d1(sheet: Sheet, prims: Sequence[Prim], t: CheckThresholds) -> tuple[CheckFailure, ...]`:
  - Pairs: dimension_line/arrowhead × dimension_line/arrowhead, and dimension_line/arrowhead × extension_line, of **different owners**.
  - A failure is `distance <= t.epsilon_mm`, with threshold = epsilon.
  - Exception: a dimension line (or arrowhead) vs an extension line where the line's own annotation has an extension line with the same `entity` that coincides with the other line within epsilon. "Coincides" means the segment distance is ≤ ε at both ends: each endpoint of one lies within ε of the other.
  - At most one failure per (owner pair, prim pair). Report the minimum-distance segment pair.
  - Extension × extension is never D1.

- [ ] **Step 1: Failing tests** (build `Sheet`s in code with a small helper `make_dim(key, line, ext_lines, text_box)` in `tests/conftest.py`):
  - `test_d1_crossing_dimension_lines`
  - `test_d1_dimension_line_crosses_other_extension`
  - `test_d1_touching_and_collinear`
  - `test_d1_epsilon_boundary`: gaps of 0.01 − 1e-9 fail, 0.01 + 1e-9 pass
  - `test_d1_same_dimension_ignored`
  - `test_d1_shared_extension_chain_ok`: two chained dimensions share an extension line on entity "e2"; no failure
  - `test_d1_extension_extension_not_failure`
  - `test_d1_arc_dimension`
  - `test_grid_pairs_match_bruteforce`: 200 random segments with seed 7; the pairs within distance 1 equal a brute-force O(n²) result
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 5: D2 and D3

**Files:** Create `checks/d2.py`, `checks/d3.py`. Test: `test_d2.py`, `test_d3.py`.

**Interfaces:**
- `check_d2(sheet, prims, t) -> tuple[CheckFailure, ...]`:
  - text_box × text_box of different owners with `quad_distance < t.text_clearance_mm`;
  - text_box × (dimension_line | extension_line | arrowhead) of a different owner with distance `< t.line_clearance_mm`.
- `check_d3(sheet, prims, t)`: text_box × edge prim with distance `< t.edge_clearance_mm`. Each failure item is `CheckItem("edge", view_key, edge_index)`.
- Both report the minimum distance per (owner, owner) pair, or per (annotation, edge index) pair.

- [ ] **Step 1: Failing tests:**
  - `test_d2_text_boxes_too_close`
  - `test_d2_threshold_boundary`: gaps of 0.5 − 1e-9 fail, 0.5 + 1e-9 pass
  - `test_d2_text_vs_other_dimension_line`
  - `test_d2_own_lines_ignored`
  - `test_d2_rotated_boxes`: two 30°-rotated boxes, 0.3 mm apart, fail
  - `test_d2_font_metric_margin_changes_verdict`: a gap of 0.55 between font-metric boxes of height 2 → after the margin it is 0.15, so the pair fails
  - `test_d3_text_over_edge`
  - `test_d3_hidden_edge_counts_when_exported`
  - `test_d3_dimension_line_over_edge_not_d3`
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.

### Task 6: D7, soft metrics and the runner

**Files:** Create `checks/d7.py`, `checks/soft_metrics.py`, `checks/runner.py`; modify `checks/__init__.py` to export the public names. Test: `test_d7.py`, `test_soft_metrics.py`, `test_runner.py`.

**Interfaces:**
- `check_d7(sheet, prims, t)`:
  - Every view outline and every annotation prim lies inside `border`. "Inside" means each vertex is at least `-epsilon` from the border, measured inward.
  - No such geometry is at distance `<= epsilon` from, or inside, any `title_block` rect.
  - Items: `CheckItem("view", key)` or `CheckItem("annotation", key)`. Distance: how far outside (≥ 0), or 0 for a title-block overlap. Threshold: epsilon.
  - One failure per item.
- `SoftMetrics(extension_crossings: int, dimension_lines_over_edges: int, view_count: int, sheet_size_mm: Vec)`, computed per sheet:
  - `extension_crossings`: extension × extension pairs of different owners with distance ≤ ε.
  - `dimension_lines_over_edges`: dimension_line × edge pairs with distance ≤ ε, counted per (annotation, edge index).
- `GeometryCheckResult(thresholds: CheckThresholds, failures: tuple[CheckFailure, ...], evaluated: tuple[str, ...] = ("D1", "D2", "D3", "D7"), soft_metrics: Mapping[str, SoftMetrics])`
  - `status(check) -> Literal["pass", "fail"]`
  - `to_json() -> JsonValue`, keyed by sheet and check
- `run_geometry_checks(snapshot: Snapshot, t: CheckThresholds = CheckThresholds()) -> GeometryCheckResult`: builds the prims once per sheet, runs D1, D2, D3 and D7, and sorts the failures with `sort_failures`.

- [ ] **Step 1: Failing tests:**
  - `test_d7_annotation_outside_border`
  - `test_d7_view_over_title_block`
  - `test_d7_inside_ok`
  - `test_soft_extension_crossings_counted`
  - `test_runner_on_fixture`: `two_dimensions.json` gives all four checks `pass`, with the fixture designed clean
  - `test_runner_finds_seeded_defects`: a copy of the fixture with one text box moved onto the other dimension's line and one note outside the border gives exactly the expected D2 and D7 failures
  - `test_runner_deterministic_under_key_order`: build the dict with reversed key order; `content_hash(result.to_json())` is equal, and running twice is equal
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite plus `uv run pytest --cov=packages/cad-drawing/src --cov-report=term -q packages/cad-drawing`. Expected: PASS, with `cad_drawing.checks` coverage ≥ 80%.

## Out of scope (next milestone)

- D5 (duplicates), D8 (title block) and D10 (rebuild), which need API state in the snapshot or the report.
- The drawing report schema, `check_drawing` / `get_drawing_report` tools, and the IPC call that produces the snapshot.
- The placement engine's predicted-geometry use of these checks (§11.6).
- Calibration on owner-approved drawings (Phase 0).
