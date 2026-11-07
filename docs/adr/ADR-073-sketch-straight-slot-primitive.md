# ADR-073: Sketch straight slot primitive

- **Status:** Accepted (owner, 2026-11-07, in the 3D part feature expansion plan)
- **Source:** [plan](../superpowers/plans/2026-11-07-sketch-straight-slot.md); specification v1.42, sections 5.7.4 and 22.4.1; checklist `SK-ENT-021`

## Context

Prior to this decision, slot-shaped sketch profiles could only be authored as manual compositions of two parallel `line` entities and two semicircular `arc` entities (`SK-ENT-021`). While composite line/arc loops produce valid profiles in SOLIDWORKS, requiring agents to manually calculate tangent offset coordinates, arc centers, and CCW direction flags is error-prone, verbose, and deviates from standard CAD practice where straight slots are primary Tier 1 sketch entities (spec §5.3.2 Tier 1, §5.7.4, §22.4.1).

## Decision

- **Add `straight_slot` entity to Part Feature Graph IR:**
  ```json
  {
    "type": "straight_slot",
    "start_point": [-20.0, 0.0],
    "end_point": [20.0, 0.0],
    "width": 20.0
  }
  ```
  - `start_point`: `[x, y]` coordinates of the first arc center in sketch plane millimeters.
  - `end_point`: `[x, y]` coordinates of the second arc center in sketch plane millimeters.
  - `width`: Full width of the slot in millimeters ($W \ge 0.01$ mm), corresponding to diameter $2r$ of the semicircular end caps.

- **Geometric Validation:**
  - Centerline length: $L = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2} \ge 0.01$ mm.
  - Slot width: $W \ge 0.01$ mm.
  - A profile for `extrude` or `cut_extrude` may consist of a single `straight_slot` primitive, which inherently defines a closed, non-self-intersecting loop.

- **Canonical Lowering & Execution:**
  - A `straight_slot` lowers deterministically into two tangent `line` entities and two semicircular `arc` entities oriented counter-clockwise (CCW):
    Let $\vec{v} = P_2 - P_1 = (\Delta x, \Delta y)$, $L = \|\vec{v}\|$, unit tangent $\hat{u} = \vec{v} / L$, unit normal $\hat{n} = (-\Delta y/L, \Delta x/L)$, radius $r = W/2$.
    - Line 1: $(P_1 - r\hat{n}) \to (P_2 - r\hat{n})$
    - Arc 1 (at $P_2$): center $P_2$, start $(P_2 - r\hat{n})$, end $(P_2 + r\hat{n})$, direction `ccw`
    - Line 2: $(P_2 + r\hat{n}) \to (P_1 + r\hat{n})$
    - Arc 2 (at $P_1$): center $P_1$, start $(P_1 + r\hat{n})$, end $(P_1 - r\hat{n})$, direction `ccw`
  - In `ExecutionServer.Adapters`, `SketchAdapter.CreateSketch` natively executes or accepts lowered lines/arcs and `straight_slot` entities with COM cleanup (`Marshal.ReleaseComObject`).

- **Face Transformation (Cap Faces):**
  - Sketches placed on `<extrude>.start_face` or `<extrude>.end_face` transform `start_point` and `end_point` following the coordinate mirroring rules of ADR-070.

## Rationale

1. **Agent Usability:** Agents writing Part Feature Graphs can specify slots concisely using centerline endpoints and width, matching standard engineering drawing callouts for slotted holes and keyways.
2. **Deterministic CCW Ordering:** Lowering to standard CCW line and arc loops guarantees loop closure without numeric drift, preserving full compatibility with `cad-verification` Green's theorem area calculation and CAD extrusion routines.
3. **Spec Alignment:** Fulfills Tier 1 requirements for `SK-ENT-021` (Straight Slot).

## Consequences

- Agents can author slot features with high clarity and minimal token overhead.
- Schema version bumps to v1.42.
