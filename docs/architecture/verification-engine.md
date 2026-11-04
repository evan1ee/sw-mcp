# 10. Verification Engine

> Specification v1.24, section 10. Index and section map: [specifications/README.md](../specifications/README.md).

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
