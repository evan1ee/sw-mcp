# Clear Post-MVP 3D Part Technical Debt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pay down the four post-MVP 3D Part Chain technical-debt items on `chore/clear-part-mvp-tech-debt` — K29 cap-face datum-plane generalization (`plane:front`, `plane:top`, `plane:right` × `start_face`, `end_face`), live 3D part test coverage (`start_face`, non-front base planes, `block_centre_hole`), prompt-to-Part-IR evaluation baseline (`score_part_ir.py` & `tests/cad-benchmark`), and C# COM interop / verification contract hygiene — without touching any 2D drawing code or tests.

**Architecture:** Preserve the pure-core / port-adapter / STA add-in layering (Guideline G1, G2, ADR-035, ADR-038, ADR-059, ADR-070). Generalize cap-face coordinate frames and 2D-to-3D projection helpers across all three standard datum planes (`plane:front`, `plane:top`, `plane:right`) and both cap roles (`start_face`, `end_face`), expose pure geometry and reference helpers in `cad-geometry` and `cad-references`, harden C# COM lifetime and error translation in `ExecutionServer.Adapters` and type validation in `cad-verification`, record the 12-case prompt-to-IR benchmark baseline under `tests/cad-benchmark`, and expand `tests/live/test_live_part_chain.py`.

**Tech Stack:** Python 3.13 (`uv`, `pytest`, `ruff`, `pyright`, `lint-imports`), C# / .NET (`ExecutionServer.Core` netstandard2.0, `ExecutionServer.Adapters` / `ExecutionServer.AddIn` net48, `ExecutionServer.Tests` net8.0 xUnit), SOLIDWORKS 2025 COM interop.

**Spec:** [`docs/specifications/README.md`](../../specifications/README.md) (v1.37), [`docs/architecture/feature-schema-guide.md`](../../architecture/feature-schema-guide.md) (§5.7.4), [`docs/adr/ADR-070-sketch-on-extrude-cap-face.md`](../../adr/ADR-070-sketch-on-extrude-cap-face.md), [`docs/specifications/open-decisions.md`](../../specifications/open-decisions.md) (K29), [`HANDOFF.md`](../../../HANDOFF.md).

## Global Constraints

- **Freeze 2D drawings (ADR-057):** Do **not** modify `packages/cad-drawing`, `standards/iso`, `drawing-*` schemas in `schemas/`, `tests/drawing-benchmark`, or any drawing live tests.
- **No new IR feature types:** Do **not** add arcs, fillets, chamfers, or linear/circular patterns (`MVP_TYPES` remains `sketch`, `extrude`, `cut_extrude`).
- **Preserve process & schema architecture (ADR-035, ADR-041):** Do **not** alter the process split between `apps/mcp-server` and `apps/core-service` or delete pre-scaffolded schemas in `schemas/`. Generated contract files (`packages/cad-ir/src/cad_ir/generated/`, `apps/execution-server/ExecutionServer.Core/Ipc/Generated/Messages.g.cs`) are updated only via `uv run python scripts/generate_contracts.py`.
- **Python layering & purity (Guideline G2):** `cad-ir`, `cad-geometry`, `cad-references`, `cad-compiler`, `cad-drawing`, `cad-verification` perform zero I/O and never import `cad_protocol`, `cad_application`, `core_service`, or `mcp_server`. `cad-ir` depends on no other workspace package.
- **C# COM object safety (Guideline G1, ADR-059):** Release temporary COM objects (`IFeature`, `IFace2`, `ISurface`, `IBody2`, `IMassProperty`, `SelectData`, `IMathTransform`, `IMathPoint`, `ISketch`, `ISketchSegment`) via `ComScope` or `Marshal.ReleaseComObject` in `finally` blocks. Never release `ISldWorks`, `IModelDoc2`, or manager objects (`ISketchManager`, `IFeatureManager`, `ISelectionMgr`, `IModelDocExtension`, `IMathUtility`). Never call `Marshal.FinalReleaseComObject`.
- **ExecutionServer.Core CAD-free (ADR-038):** Zero SOLIDWORKS interop references in `ExecutionServer.Core`; enforced by `BannedSymbols.txt`.

## Review Focus

1. **Non-front base plane cap-face normal & offset matching (`plane:top` along +Y/-Y, `plane:right` along +X/-X):** `FaceSignature.Match` and `face_frame` must compute signed plane offset along the face's outward unit normal (`offset_mm = depth` on `end_face`, `0.0` on `start_face`) and mirror `x_axis` on `start_face` for all 3 datum planes, not just `plane:front`.
2. **Asymmetric cut coordinates on `start_face` across `plane:top` and `plane:right`:** `in_base_frame` and `expected_geometry` (`FaceFrame.to_model`) must project `(x, y)` on `start_face` to `(-x) * base.x_axis + y * base.y_axis` so off-center holes land at the exact 3D center of mass and cylinder axis on `plane:top` and `plane:right`.
3. **Malformed observation types in per-operation verification (`cad_verification/api/contracts.py`):** In Python `isinstance(False, int)` is `True` and `False == 0` is `True`; `_eval_status_ok`, `_eval_not_suppressed`, and `_eval_exact_field` must reject boolean/int type mismatches with `status="not_evaluated", reason="malformed_data"` rather than silently passing.
4. **COM wrapper & untitled document leaks on failure in `ExecutionServer.Adapters/Parts`:** If `PartCreationAdapter.CreatePart` fails during `SaveAs4` after `NewDocument`, the untitled document must be closed via `_sw.CloseDoc`. Every `FirstFeature()` / `GetNextFeature()` traversal in `FeatureLookup`, `SketchAdapter`, `FeatureAdapter`, and `PartMeasureAdapter` must release intermediate `IFeature` wrappers via `ComScope`.
5. **Unclosed `.SLDPRT` handles when a live test fails mid-execution:** Every test in `tests/live/test_live_part_chain.py` must close any target, working, or `.failed.<job_id>.SLDPRT` document in SOLIDWORKS inside its `finally:` block.

---

### Task 1: Generalize Cap-Face Coordinate Frames & Reference Resolution Across All 6 Datum-and-Cap Combinations (Debt 1)

**Files:**
- Modify: `packages/cad-ir/src/cad_ir/part_feature_graph/faces.py`
- Modify: `packages/cad-geometry/src/cad_geometry/__init__.py`
- Modify: `packages/cad-geometry/src/cad_geometry/signatures/__init__.py`
- Modify: `packages/cad-references/src/cad_references/__init__.py`
- Modify: `packages/cad-references/src/cad_references/semantic/__init__.py`
- Modify: `packages/cad-verification/src/cad_verification/part.py`
- Modify: `packages/cad-application/src/cad_application/authoring_guide.py`
- Modify: `apps/execution-server/ExecutionServer.Core/Parts/FaceSignature.cs`
- Modify: `tests/live/spikes/PartChainSpike/FaceSpike.cs`
- Test: `packages/cad-ir/tests/test_faces.py`
- Create: `packages/cad-geometry/tests/test_cap_face_frames.py`
- Create: `packages/cad-references/tests/test_cap_face_refs.py`
- Modify: `packages/cad-compiler/tests/test_face_sketch.py`
- Modify: `packages/cad-compiler/tests/test_face_lowering.py`
- Modify: `packages/cad-verification/tests/test_part.py`
- Modify: `packages/cad-application/tests/test_authoring_guide.py`
- Modify: `apps/execution-server/ExecutionServer.Tests/Parts/FaceSignatureTests.cs`

**Interfaces:**
- Produces in `cad_ir.part_feature_graph.faces`:
  - `FaceFrame.to_model(self, x: float, y: float, depth_from_base: float | None = None) -> tuple[float, float, float]` — maps 2D face sketch coordinates `(x, y)` to 3D model coordinates `(X, Y, Z)` using `self.x_axis`, `self.y_axis`, and `self.base_normal * (self.offset_mm if depth_from_base is None else depth_from_base)`.
- Produces in `cad_geometry.signatures` (re-exported in `cad_geometry`):
  - `CapFaceSignature` / `cap_face_frame(plane: str, depth: float, role: str) -> FaceFrame` and `project_cap_face_point(plane: str, depth: float, role: str, x: float, y: float, into_body_mm: float = 0.0) -> tuple[float, float, float]`.
- Produces in `cad_references.semantic` (re-exported in `cad_references`):
  - `FaceRef`, `SUPPORTED_ROLES`, `parse_face_plane(plane: str) -> FaceRef | None`, `resolve_cap_face_signature(graph: PartGraph, plane: str) -> dict[str, Any] | None`.

- [ ] **Step 1: Write failing parameterized unit tests across all 6 datum-and-cap combinations (`plane:front`, `plane:top`, `plane:right` × `start_face`, `end_face`) in Python and C#**

Add parameterized tests in:
- `packages/cad-ir/tests/test_faces.py`: test `face_frame` and `FaceFrame.to_model` for all 6 `(plane, role)` combinations:
  - `("plane:front", "end_face")` -> `x=(1,0,0), y=(0,1,0), normal=(0,0,1), offset=10, to_model(10,5)=(10,5,10)`
  - `("plane:front", "start_face")` -> `x=(-1,0,0), y=(0,1,0), normal=(0,0,-1), offset=0, to_model(10,5)=(-10,5,0)`
  - `("plane:top", "end_face")` -> `x=(1,0,0), y=(0,0,-1), normal=(0,1,0), offset=10, to_model(10,5)=(10,10,-5)`
  - `("plane:top", "start_face")` -> `x=(-1,0,0), y=(0,0,-1), normal=(0,-1,0), offset=0, to_model(10,5)=(-10,0,-5)`
  - `("plane:right", "end_face")` -> `x=(0,0,-1), y=(0,1,0), normal=(1,0,0), offset=10, to_model(10,5)=(10,5,-10)`
  - `("plane:right", "start_face")` -> `x=(0,0,1), y=(0,1,0), normal=(-1,0,0), offset=0, to_model(10,5)=(0,5,10)`
- `packages/cad-geometry/tests/test_cap_face_frames.py`: test `cap_face_frame` and `project_cap_face_point` across all 6 `(plane, role)` combinations.
- `packages/cad-references/tests/test_cap_face_refs.py`: test `parse_face_plane` and `resolve_cap_face_signature` across all 6 `(plane, role)` combinations.
- `packages/cad-compiler/tests/test_face_sketch.py` and `test_face_lowering.py`: parameterize validation and lowering across all 6 `(base_plane, role)` combinations.
- `packages/cad-verification/tests/test_part.py`: parameterize `expected_geometry` across all 6 `(base_plane, role)` combinations with an off-center blind hole `(10, 5)`, asserting exact volume, surface area, 3D center of mass, and cylinder point/direction.
- `apps/execution-server/ExecutionServer.Tests/Parts/FaceSignatureTests.cs`: add `[Theory]` with `[MemberData]` covering all 6 `(plane, role)` combinations for `FaceSignature.Match` and `FaceSignature.FrameMatches`.

- [ ] **Step 2: Run Python and C# tests to verify they fail**

Run:
`uv run pytest packages/cad-ir/tests/test_faces.py packages/cad-geometry packages/cad-references packages/cad-compiler/tests/test_face_lowering.py packages/cad-verification/tests/test_part.py -v`
`dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj --filter FaceSignatureTests`
Expected: FAIL (`FaceFrame.to_model`, `cad_geometry.signatures`, `cad_references.semantic` not yet defined).

- [ ] **Step 3: Implement `FaceFrame.to_model`, `cad_geometry.signatures`, `cad_references.semantic`, and update `part.py`, `authoring_guide.py`, and `FaceSpike.cs`**

1. In `packages/cad-ir/src/cad_ir/part_feature_graph/faces.py`:
   - Add `to_model(self, x: float, y: float, depth_from_base: float | None = None) -> tuple[float, float, float]` on `FaceFrame` that projects `(x, y)` along `self.x_axis` and `self.y_axis` and shifts along `self.base_normal` by `self.offset_mm if depth_from_base is None else depth_from_base`.
2. In `packages/cad-geometry/src/cad_geometry/signatures/__init__.py` and `packages/cad-geometry/src/cad_geometry/__init__.py`:
   - Implement `cap_face_frame(plane: str, depth: float, role: str) -> FaceFrame` and `project_cap_face_point(plane: str, depth: float, role: str, x: float, y: float, into_body_mm: float = 0.0) -> tuple[float, float, float]`.
3. In `packages/cad-references/src/cad_references/semantic/__init__.py` and `packages/cad-references/src/cad_references/__init__.py`:
   - Expose `FaceRef`, `SUPPORTED_ROLES`, `parse_face_plane`, and implement `resolve_cap_face_signature(graph: PartGraph, plane: str) -> dict[str, Any] | None`.
4. In `packages/cad-verification/src/cad_verification/part.py`:
   - Use `frame.to_model(center_x, center_y, depth_center)` and `frame.to_model(entity.center[0], entity.center[1])` so 2D-to-3D projection uses `FaceFrame.to_model` directly across all planes and cap roles.
5. In `packages/cad-application/src/cad_application/authoring_guide.py` and `tests/test_authoring_guide.py`:
   - Update the "Sketching on a cap face" section so it documents `end_face` and `start_face` across all three standard planes (`plane:front`, `plane:top`, `plane:right`) without a `plane:front`-only restriction.
6. In `tests/live/spikes/PartChainSpike/FaceSpike.cs`:
   - Generalize `BuildBlock` and `PickFace` to accept plane index `(0=front, 1=top, 2=right)` and expected normal vector instead of hardcoding `RefPlanes(doc)[0]` and `n[2]`.

- [ ] **Step 4: Run unit tests in Python and C# to verify they pass**

Run:
`uv run pytest packages/cad-ir/tests/test_faces.py packages/cad-geometry packages/cad-references packages/cad-compiler/tests/test_face_sketch.py packages/cad-compiler/tests/test_face_lowering.py packages/cad-verification/tests/test_part.py packages/cad-application/tests/test_authoring_guide.py -v`
`dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add packages/cad-ir packages/cad-geometry packages/cad-references packages/cad-compiler packages/cad-verification packages/cad-application apps/execution-server/ExecutionServer.Core apps/execution-server/ExecutionServer.Tests tests/live/spikes/PartChainSpike/FaceSpike.cs
git commit -m "feat: generalize cap-face sketch frames across all datum planes (K29)"
```

---

### Task 2: Harden 3D Part C# COM Interop Cleanup & Verification Contract Hygiene (Debt 4)

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureLookup.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/CapFaceSketch.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/SketchAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/FeatureAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/PartCreationAdapter.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/Parts/PartMeasureAdapter.cs`
- Modify: `packages/cad-verification/src/cad_verification/api/contracts.py`
- Test: `packages/cad-verification/tests/test_contracts.py`
- Test: `apps/execution-server/ExecutionServer.Tests/Parts/PartUnitsTests.cs`

**Interfaces:**
- `FeatureLookup.FindById(IModelDoc2 doc, string featureId, ComScope? scope = null) -> IFeature?` — releases every non-matching `IFeature` visited during traversal and tracks the returned `IFeature` in `scope` when provided.
- `PartCreationAdapter.CreatePart` — closes the untitled document via `_sw.CloseDoc` in a `try/catch` block if `SaveAs4` fails after `NewDocument` succeeds.
- `FeatureAdapter.CreateFeature` & `FeatureAdapter.Rebuild` — wraps COM calls in `COMException` translation to `IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, ...)` with `effect` (`"none"`, `"applied"`, or `"unknown"`) and `stage` (`"invoke"` or `"verify"`), and tracks all temporary `IFeature` wrappers (`profileFeature`, `createdFeature`, parent features, and traversal features) in `ComScope`.
- `cad_verification.api.contracts.evaluate` — validates strict runtime types (`bool` vs `int`) on `observation` fields (`is_warning`, `error_code`, `suppressed`, `entity_count`, `type`), returning `status="not_evaluated", reason="malformed_data"` on type mismatches.

- [ ] **Step 1: Write failing tests for malformed observation types in `packages/cad-verification/tests/test_contracts.py`**

Add tests in `packages/cad-verification/tests/test_contracts.py`:
- `test_boolean_error_code_is_malformed_not_passed`: `observation={"type": "extrude", "error_code": False, "is_warning": False, "suppressed": False}` -> `status_ok` check must have `status == "not_evaluated"` and `reason == "malformed_data"` (not `"passed"`).
- `test_non_boolean_suppressed_or_is_warning_is_malformed`: `suppressed=0` or `is_warning="false"` -> `status == "not_evaluated"`, `reason == "malformed_data"`.
- `test_boolean_entity_count_is_malformed`: `entity_count=True` when `expected=1` -> `status == "not_evaluated"`, `reason == "malformed_data"`.

- [ ] **Step 2: Run `pytest` on `test_contracts.py` to verify it fails**

Run: `uv run pytest packages/cad-verification/tests/test_contracts.py -v`
Expected: FAIL (`False == 0` and `True == 1` evaluate to `"passed"`).

- [ ] **Step 3: Harden `contracts.py` and C# Part Adapters (`FeatureLookup`, `CapFaceSketch`, `SketchAdapter`, `FeatureAdapter`, `PartCreationAdapter`, `PartMeasureAdapter`)**

1. In `packages/cad-verification/src/cad_verification/api/contracts.py`:
   - In `_eval_status_ok`: if `"is_warning"` is present and not `isinstance(..., bool)`, or if `error_code` is `isinstance(..., bool)` or not `isinstance(..., int)`, return `status="not_evaluated", reason="malformed_data"`.
   - In `_eval_not_suppressed`: if ` not isinstance(suppressed, bool)`, return `status="not_evaluated", reason="malformed_data"`.
   - In `_eval_exact_field`: if `type(measured) is not type(check.expected)` (e.g. `bool` vs `int`), return `status="not_evaluated", reason="malformed_data"`.
2. In `apps/execution-server/ExecutionServer.Adapters/Parts/`:
   - `FeatureLookup.cs`: release non-matching `IFeature` objects during `FirstFeature()` / `GetNextFeature()` loop; accept optional `ComScope? scope = null` to track the matched feature; remove duplicate `FindFeatureById` from `FeatureAdapter.cs`.
   - `CapFaceSketch.cs`: pass `scope` to `FeatureLookup.FindById(doc, face.Feature, scope)`.
   - `SketchAdapter.cs`: track `targetPlane`, all non-matching/unused `IFeature` objects in `ResolveAndVerifyPlane`, and `sketchFeature` in `CreateSketch` via `ComScope`.
   - `FeatureAdapter.cs`: track `profileFeature`, `createdFeature`, parent `IFeature` objects, and `Rebuild` loop `IFeature` objects in `ComScope`; translate `COMException` during feature creation / rebuild into `IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, ...)` with `effect` and `stage`.
   - `PartCreationAdapter.cs`: if `SaveAs4` fails after `NewDocument`, close the untitled document (`_sw.CloseDoc(title)`) before throwing `IpcException`.
   - `PartMeasureAdapter.cs`: track `mass` and feature-tree `IFeature` objects in `ComScope`.

- [ ] **Step 4: Run verification tests and full C# solution build**

Run:
`uv run pytest packages/cad-verification/tests/test_contracts.py -v`
`dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
`dotnet build apps/execution-server/ExecutionServer.sln`
`uv run python scripts/generate_contracts.py --check`
Expected: PASS with 0 warnings and 0 errors.

- [ ] **Step 5: Commit Task 2**

```bash
git add packages/cad-verification apps/execution-server/ExecutionServer.Adapters
git commit -m "fix: harden 3D part COM lifetime cleanup and verification contract type checks"
```

---

### Task 3: Establish the Prompt-to-Part-IR Evaluation Baseline (`score_part_ir.py` & `tests/cad-benchmark`) (Debt 3)

**Files:**
- Modify: `packages/cad-application/src/cad_application/authoring_eval/cases.py`
- Modify: `packages/cad-application/src/cad_application/authoring_eval/references.py`
- Modify: `scripts/score_part_ir.py`
- Create: `tests/cad-benchmark/part_ir_baseline_answers.json`
- Create: `tests/cad-benchmark/test_part_ir_benchmark.py`
- Modify: `packages/cad-application/tests/test_authoring_eval.py`

**Interfaces:**
- `tests/cad-benchmark/part_ir_baseline_answers.json`: canonical JSON mapping every `case_id` in `CASES` to its evaluated Part Feature Graph IR (or `null` for refusal cases), including start-face and non-front plane coverage.
- `scripts/score_part_ir.py`: supports `--prompts`, `--baseline` (scores `tests/cad-benchmark/part_ir_baseline_answers.json`), and `<answers.json>`.

- [ ] **Step 1: Write failing benchmark test in `tests/cad-benchmark/test_part_ir_benchmark.py`**

Create `tests/cad-benchmark/test_part_ir_benchmark.py` testing:
1. `uv run python scripts/score_part_ir.py --prompts` lists all benchmark prompts cleanly with exit code `0`.
2. `tests/cad-benchmark/part_ir_baseline_answers.json` exists, covers every case in `CASES` (including `blind_hole_start_face` in addition to `blind_hole_top_face` and `block_centre_hole`), and `main([str(BASELINE_JSON)])` in `scripts/score_part_ir.py` exits with `0` (`100%` pass rate).

- [ ] **Step 2: Run `pytest tests/cad-benchmark/test_part_ir_benchmark.py` to verify it fails**

Run: `uv run pytest tests/cad-benchmark/test_part_ir_benchmark.py -v`
Expected: FAIL (`part_ir_baseline_answers.json` not yet created).

- [ ] **Step 3: Add `blind_hole_start_face` to `cases.py` / `references.py`, generate `tests/cad-benchmark/part_ir_baseline_answers.json`, and run `score_part_ir.py`**

1. Add `blind_hole_start_face` case to `packages/cad-application/src/cad_application/authoring_eval/cases.py` and `references.py` (13 cases total: 10 build, 3 refuse).
2. Write `tests/cad-benchmark/part_ir_baseline_answers.json` containing the validated baseline answers for all 13 benchmark cases.
3. Support `--baseline` in `scripts/score_part_ir.py` (defaulting to `tests/cad-benchmark/part_ir_baseline_answers.json` when `--baseline` is passed).

- [ ] **Step 4: Run `score_part_ir.py` and `pytest` to verify they pass**

Run:
`uv run python scripts/score_part_ir.py --prompts`
`uv run python scripts/score_part_ir.py tests/cad-benchmark/part_ir_baseline_answers.json`
`uv run pytest packages/cad-application/tests/test_authoring_eval.py tests/cad-benchmark/test_part_ir_benchmark.py -v`
Expected: `13/13 passed` (exit code 0).

- [ ] **Step 5: Commit Task 3**

```bash
git add packages/cad-application/src/cad_application/authoring_eval packages/cad-application/tests/test_authoring_eval.py scripts/score_part_ir.py tests/cad-benchmark
git commit -m "test: establish prompt-to-part-IR benchmark baseline in tests/cad-benchmark"
```

---

### Task 4: Close 3D Part Live Test Coverage Gaps (`start_face`, `plane:top`, `plane:right`, `block_centre_hole`) & Document Cleanup (Debt 2 & Debt 4)

**Files:**
- Modify: `tests/live/test_live_part_chain.py`
- Modify: `docs/architecture/feature-schema-guide.md`
- Modify: `docs/specifications/open-decisions.md`
- Modify: ` docs/adr/ADR-070-sketch-on-extrude-cap-face.md`
- Modify: ` docs/specifications/README.md` (and topic headers + `CHANGELOG.md` if spec §5.7.4 changes)
- Modify: `HANDOFF.md`

**Interfaces:**
- New live tests in `tests/live/test_live_part_chain.py`:
  - `test_blind_hole_in_start_face(tmp_path: Path) -> None`: builds a 40 × 30 × 10 mm block on `plane:front` with an off-center Ø5 × 4 mm blind hole on `extrude_base.start_face` (`center=[10, 5]`, verifying mirrored `x = -10` in model space), reaches `COMMITTED`, and passes all in-session and reopened verification checks.
  - `test_blind_hole_on_non_front_base_planes(tmp_path: Path, base_plane: str, face_role: str) -> None` (parameterized over `plane:top` and `plane:right` × `end_face` and `start_face`): builds a 40 × 30 × 10 mm block on `plane:top` and `plane:right` with a Ø5 × 4 mm blind hole on `extrude_base.<face_role>`, reaches `COMMITTED`, and passes all checks.
  - `test_block_centre_hole_end_to_end(tmp_path: Path) -> None`: builds `REFERENCE_ANSWERS["block_centre_hole"]` (40 × 30 × 10 mm block with Ø5 mm through-hole), reaches `COMMITTED`, and passes all checks.
- Ensure every test in `tests/live/test_live_part_chain.py` closes any open target/working/failed `.SLDPRT` in SOLIDWORKS inside its `finally:` block.

- [ ] **Step 1: Add the new 3D part live tests and `finally:` document cleanup to `tests/live/test_live_part_chain.py`**

Add `test_blind_hole_in_start_face`, `test_blind_hole_on_non_front_base_planes`, and `test_block_centre_hole_end_to_end` in `tests/live/test_live_part_chain.py`, and ensure `_close_in_solidworks_by_path` is called in `finally:` blocks across all tests in `test_live_part_chain.py`.

- [ ] **Step 2: Run non-live and (if SOLIDWORKS 2025 is open) live test suites**

Run:
`uv run pytest --ignore=tests/drawing-benchmark`
`uv run pytest tests/live/test_live_part_chain.py -m live -v` (skips cleanly if SOLIDWORKS 2025 is not running; executes against live SOLIDWORKS 2025 when open).

- [ ] **Step 3: Update `docs/` and `HANDOFF.md` with K29 resolution, benchmark baseline, and verification counts**

Update `HANDOFF.md` (and `docs/architecture/feature-schema-guide.md` §5.7.4 / `docs/specifications/open-decisions.md` K29 / spec version bump if §5.7.4 is edited) with the cleared tech-debt items, `score_part_ir.py` pass rate (`13/13`), and updated test counts.

- [ ] **Step 4: Run all mandatory quality gates**

Run:
1. `uv run python scripts/generate_contracts.py && git diff --exit-code packages/cad-protocol apps/execution-server`
2. `uv run ruff check .`
3. `uv run ruff format --check`
4. `uv run pyright`
5. `uv run lint-imports`
6. `uv run pytest --ignore=tests/drawing-benchmark`
7. `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`
8. `dotnet build apps/execution-server/ExecutionServer.sln`
9. `uv run pytest tests/live/test_live_part_chain.py -m live -v`
Expected: All exit with code `0`.

- [ ] **Step 5: Commit Task 4**

```bash
git add tests/live/test_live_part_chain.py docs/ HANDOFF.md
git commit -m "test: add start_face, non-front plane, and block_centre_hole live tests and update handoff"
```
