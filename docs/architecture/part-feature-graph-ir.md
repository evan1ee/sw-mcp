# 5. Part Feature Graph IR and Assembly Graph IR

> Specification v1.35, section 5.1–5.5. Index and section map: [specifications/README.md](../specifications/README.md).

## 5.1 Purpose

The Part Feature Graph IR describes *how* a parametric part is built: a CAD-neutral representation of operations and dependencies. The reference implementation has a working Feature Graph IR. This design learns from it but defines its own schema.

The graph describes feature identity, type, parameters, input references, dependencies, geometric references, suppression state, configuration context and feature-specific metadata. Two more fields connect it to other modules (section 3.3):

- `realizes` lists the Design Intent functional features a node produces, for example `"realizes": ["bearing_bore"]`.
- `origin` is `built` (compiled and executed by this system) or `read` (taken from the feature tree of a hand-modelled part; never executed).

## 5.2 Graph Structure

A directed acyclic graph: nodes are operations, edges are dependencies.

```
Part
 ├── Sketch_Base
 │    └── Extrude_Base
 │         ├── Sketch_Hole
 │         │    └── Cut_Hole
 │         └── Fillet_Edges
```

Required: stable unique feature IDs, dependency validation, cycle detection, topological sort, feature replacement / suppression / deletion, graph diff, graph versioning.

## 5.3 Feature Taxonomy and Coverage

### 5.3.1 Coverage principle

SOLIDWORKS has hundreds of feature types. Supporting all of them is neither needed nor affordable: each type costs implementation, tests and agent tokens (section 12.3). Coverage is therefore **driven by the benchmarks and drawing profiles**: a feature type enters a tier only when a benchmark part or a drawing profile needs it. Anything else is either a later tier or explicitly out.

Two levels of support:

- **Create** — the type exists in the Part Feature Graph IR; the compiler lowers it and the executor builds it.
- **Read** — the type is recognized in an existing (hand-modelled) part: its driving dimensions and drawing-relevant data (hole type, thread, bend data, draft) are extracted for the drawing pipeline and verification. The result is a read-only Feature Graph whose nodes carry `origin: read` (section 3.3).

Read is much cheaper than Create and is needed for hand-modelled parts (section 11.1), so Read coverage is wider. In addition, **any** feature, recognized or not, gets **generic dimension read**: its display dimensions are enumerated through the SOLIDWORKS API so D4 completeness works even on unrecognized features. Unrecognized features are reported by name and type, never silently ignored.

The IR describes **final sketch geometry**, not editing steps. Interactive sketch tools (trim, extend, split entities) are not IR operations; the agent states the resulting lines and arcs directly. This keeps the IR smaller and deterministic.

### 5.3.2 Tier 1 — Phase 1 (drawings)

**Phase 1 is Read-first (ADR-029) [Builder's call].** The drawing pipeline works mostly on hand-modelled parts, so Phase 1 delivers Read for every Tier 1 feature (Phase 1b), plus Create only for the features that the IR-built drawing benchmark parts use (Phase 1c; the table below the feature list). Create for the rest of the "Create + Read" column moves to Phase 2.

| Group | Create + Read | Read only |
| --- | --- | --- |
| Document / body | CreatePart, SetMaterial, SetCustomProperties, CombineBodies, DeleteBody | SplitBody, Move/Copy Body, Configurations (list, active, derived, configuration-specific dimensions and properties), imported bodies (recognized as featureless; see 11.1) |
| Sketch | Line, Centerline (construction), Circle, Arc (center, 3-point, tangent), Rectangle (corner, center), StraightSlot, Polygon, Point, SketchFillet, SketchChamfer, OffsetEntities, ConvertEntities, MirrorSketch, SketchConstraint, SketchDimension | Spline, Ellipse, sketch patterns, 3D sketch, text |
| Solid | Extrude and CutExtrude (blind, through all, up to next, up to surface, mid-plane, thin), Revolve and CutRevolve, Shell (uniform), Fillet (constant radius), Chamfer (distance–distance, angle–distance), Draft (neutral plane), Rib, LinearPattern, CircularPattern, Mirror | Sweep, Loft, variable/face/full-round fillet, other draft types, sketch/curve/table/fill patterns, Dome |
| Holes and threads | HoleWizard (simple, counterbore, countersink, tapped; ISO metric), CosmeticThread | Thread feature, legacy Hole |
| Molded support | SplitLine (parting line) | Mounting Boss, Snap Hook, Lip/Groove, Vent |
| Sheet metal | SheetMetalParameters (thickness, bend radius, K-factor or bend table), BaseFlange/Tab, EdgeFlange, SketchedBend, ClosedCorner, BreakCorner/Relief, FlatPattern | MiterFlange, Hem, Jog, Unfold/Fold, Forming tools, Louvers, Gussets, Convert to Sheet Metal, Insert Bends (common on hand-modelled brackets) |
| Reference geometry | Plane (offset, angle, through entities), Axis, Point, CoordinateSystem | — |
| Equations | — | Equations, global variables and linked dimensions (`IEquationMgr`, link values). A dimension driven by an equation or link is derived, not a driving parameter (D4); the driving global variable or dimension is |

Tier 1 maps to the drawing benchmark (section 11.8):

| Benchmark part | Tier 1 features it needs |
| --- | --- |
| Plate with hole pattern | Extrude, HoleWizard, LinearPattern, Chamfer |
| Turned shaft with threads and fits | Revolve, Chamfer, CosmeticThread, CutExtrude (keyway), Plane |
| Bent bracket | SheetMetalParameters, BaseFlange, EdgeFlange, SketchedBend, HoleWizard, FlatPattern |
| Molded housing | Extrude, Shell, Draft, Fillet, Rib, Extrude (bosses), SplitLine |
| Dense-feature part | HoleWizard, CircularPattern, LinearPattern, Mirror |

Hand-modelled benchmark parts may use Read-only features. That is how Read coverage is tested.

### 5.3.3 Tier 2 — Phase 2 (CAD benchmark)

Create support for: Sweep, SweptCut, Loft, LoftedCut, Helix, EquationCurve (for gear involutes), Spline, Ellipse, MiterFlange, Hem, Jog, variable and full-round fillets, Draft (parting line, step), sketch-driven and curve-driven patterns, SplitBody, Dome, Equations and global variables.

Each item must be required by a part in the CAD benchmark (section 15.4: spring → Helix + Sweep, gear → EquationCurve, and so on). If no benchmark part needs it, it moves to Tier 3.

### 5.3.4 Tier 3 — later

Configurations (Create) and design tables, fastening features (Create), feature reorder and rollback (with Phase 4 editing), surface features (offset, knit, trim, thicken), Wrap, Flex, Deform, Indent, Scale, 3D sketch (Create).

### 5.3.5 Explicitly out of scope

Weldments, mold tooling (core/cavity, tooling split), Toolbox and library features (Create), direct-edit features (move face, delete face), routing, FeatureWorks recognition of imported bodies. If a part contains these, the drawing pipeline uses generic dimension read and reports them as unrecognized.

### 5.3.6 Rules

- Unsupported feature types produce explicit compiler errors, never approximate geometry.
- Adding a feature type adds an IR schema entry, a lowering rule, an executor adapter and a test. It **never adds an MCP tool** (section 12.3).
- **Language-independent identification (ADR-021).** Feature, plane and dimension names depend on the SOLIDWORKS UI language and on what users rename them to. For example, `Boss-Extrude1` and `Front Plane` are called `凸台-拉伸1` and `前视基准面` on a Chinese install. The Read path identifies features by `IFeature.GetID()` and their type by `IFeature.GetTypeName2`, never by display name or tree position: positions change whenever a feature is inserted or reordered. Phase 0 confirms that `GetID()` stays stable across save/reopen, rename and rebuild, and falls back to a persistent reference (`GetPersistReference3`) for any case where it does not. The 2026-11-05 spike confirmed it on a plate (A2): `GetID()` was identical for all 20 features after close and reopen, so the fallback is not needed for the MVP and stays documented here. Dimensions are identified by their owning feature's ID plus the dimension's index within that feature. It identifies the three standard planes and the origin by their order among the reference planes, never by display name. The IR names standard planes by role (`Front`, `Top`, `Right`), and the executor maps each role to the native plane. Display names are kept only for reporting.
- Phase 0 maps the reference implementation's feature support onto these tiers. Anything it can create belongs in Tier 1 or 2 unless the owner decides otherwise.

## 5.4 Example (illustrative)

```json
{
  "module": "part", "id": "cylinder", "schema_version": "0.1", "units": "mm", "origin": "built",
  "nodes": {
    "sketch_base": { "type": "sketch", "plane": "plane:front",
      "entities": { "c1": { "type": "circle", "center": [0, 0], "diameter": 20 } },
      "dimensions": { "dia": { "type": "diameter", "entities": ["c1"], "value": 20 } } },
    "extrude_base": { "type": "extrude", "dependencies": ["sketch_base"], "profile": "sketch_base",
      "end_condition": { "type": "blind", "depth": 50 }, "realizes": ["base_face"] }
  }
}
```

Field conventions, shared objects, sketches, roles and defaults are in 5.7; the Read path for hand-modelled parts is 5.8.

## 5.5 IR Requirements

Versioned, explicitly typed, validatable without SOLIDWORKS, serializable, deterministic, CAD-neutral at the semantic level, extensible through backend capabilities, and able to represent unsupported operations without misinterpreting them. Backend-specific data lives in explicit extension fields.
