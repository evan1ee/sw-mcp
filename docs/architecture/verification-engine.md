# 10. Verification Engine

> Specification v1.32, section 10. Index and section map: [specifications/README.md](../specifications/README.md).

## 10.1 Purpose

Verification is a core capability. A successful API call does not prove the intended geometry or drawing was produced.

## 10.2 Layers

| Layer | Question | Checks | Priority |
| --- | --- | --- | --- |
| 1. API | Did SOLIDWORKS execute it? | Operation success, feature status, rebuild errors/warnings, document state, feature tree, save | **P0** (Phase 1c builds benchmark parts) |
| 2. Geometry | Is the geometry right? | Body counts, bounding box, volume, area, center of mass, dimensions, hole positions, relationships, topology | P1 |
| 3. Design intent | Does it meet the requirements? | Dimensional constraints, wall thickness, draft, hole spacing, clearance, interference, manufacturing constraints | P2 |
| 4. Drawing | Is the drawing production-ready? | Section 11.5 | **P0** |

Example: a housing builds without errors and its volume matches, but one local wall is 0.8 mm against a 2 mm minimum → API PASS, Geometry PASS, Design Intent FAIL. A model can be geometrically valid without being engineering-correct.

Each result includes: requirement ID, measured value, expected value or range, tolerance, pass/fail, measurement method, diagnostics.

### 10.2.1 Part chain MVP checks [Builder's call]

The `plan` job (8.4.1) measures the part in SOLIDWORKS with `part.measure` (8.7) and compares it with `expected_geometry(graph)`, computed from the IR alone, never from SOLIDWORKS. Both live in `packages/cad-verification` (pure). `compare(expected, measured, tolerances)` returns one result per check with the requirement, measured value, expected value, tolerance and pass or fail, and runs every comparison so that all failures are reported at once.

| Check | Pass condition |
| --- | --- |
| Operations | Every outcome succeeded, and every contract was met (10.2.2) |
| Rebuild | `rebuild.ok`, no errors |
| Features | Exactly the expected solid features and sketches, matched by `feature_id` (`f<GetID()>`, 5.3.6) and type, each healthy: its status is `ok`, so in the MVP a native warning fails it (ADR-064). An extra feature fails |
| Bodies | Exactly the expected solid body count |
| Bounding box | Within ±0.01 mm per axis |
| Volume | Within ±0.01% |
| Surface area | Within ±0.01% |
| Center of mass | Within ±0.01 mm per axis |
| Cylinders | One-to-one with the IR's circles: axis position (perpendicular to the axis) and radius within ±0.01 mm, axis direction parallel |
| Reopen | All of the above again, on a new `instance_id` after a read-only reopen, and `dirty` is false |

Any failure ends the job FAILED with `PART_VERIFICATION_FAILED` (ADR-037), whose `details` hold the failing checks. The tolerances are the owner's confirmed choice (design D3). The spike measured the plate with no difference beyond 1.4e-20 m³ from the exact values, and `GetBodyBox` equal to the true box on prismatic planar geometry; for a curved body it may be looser, which is not yet tested (open decision K12). Verification cannot catch a graph that is valid but is not the part you meant, so the job's final response lists the measured size, volume and feature count.

### 10.2.2 Per-operation verification ([ADR-064](../adr/ADR-064-per-operation-verification-contracts.md))

**Not built yet.** `cad-verification` has no contracts or evaluator, operation results have no `observation`, and the compiler still emits `dir`. Roadmap A0 and A2 and MVP Tasks 8 to 9b deliver them.

A `plan` job judges every operation before it sends the next, so a failure names its node and check.

1. Before execution, the pure `feature_contracts(graph)` gives each node its contract, from the IR alone. The compiler never computes it, and the plan holds no expected values, so a lowering error cannot agree with itself.
2. The job journals `batch_sent` and sends one operation.
3. The add-in runs it and reads back in the same command, returning `observation` with the result (8.9.3).
4. The job journals `op_result`, then the pure `evaluate(contract, observation)` judges it, and the job journals `op_verified` (13.2.3).
5. The job continues only if every required check passed. Otherwise it fails, and later operations stay `not_attempted`, with `blocked_by` in the evidence. There is no partial continuation.

| Tier | When | Facts |
| --- | --- | --- |
| T0 | Every operation | Feature ID and type, error code and warning flag, suppression, direct parents, sketch entity count, document update stamp |
| T1 | Every solid feature, once K15 clears them | Feature parameters (depth, end condition), rebuild-needed state, solid body count |
| T2 | Verification points, off by default until K18 is measured | Volume change against the IR |
| T3 | Final only (10.2.1) | Full measurement, in session and after reopen |

A contract states its `level`: `exact`, `bounded`, `declared` or `structural` (K16). Only `exact` is used until K16 is decided. A check may be marked optional: until K15 closes, `parameter_equals` is optional and reports `not_evaluated` with `unsupported`, so a parameter error is caught only by the final checks, and one with no measured effect is not caught.

Failures are classified in evidence as `compilation`, `execution`, `feature_verification` or `final_verification` (8.9.6). A successful API call is never evidence that a check passed.

## 10.3 Example (geometry)

Cylinder Ø20 × 50 mm, one solid body. Expected volume V = π · 10² · 50 ≈ 15707.96 mm³.

| Property | Expected |
| --- | --- |
| Solid bodies | 1 |
| Diameter / height | 20 mm / 50 mm |
| Volume | 15707.96 mm³ |
| Rebuild | Successful |
| Feature tree | Expected features present |
| Save/reopen | Still valid |

Numerical comparisons use configurable tolerances.

## 10.4 On Failure

Record the failed requirement, capture actual values, identify the responsible feature or chain, emit a structured diagnostic, decide whether automatic repair is safe, and request intervention when needed. **Never report success when a required check failed.**
