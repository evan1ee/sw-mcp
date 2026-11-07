# ADR-072: Sketch rectangle primitives (corner and center rectangles)

- **Status:** Accepted (owner, 2026-11-07, in the 3D part feature expansion plan)
- **Source:** [plan](../superpowers/plans/2026-11-07-sketch-rectangles.md); specification v1.41, sections 5.7.4 and 22.4.1; checklists `SK-ENT-005`, `SK-ENT-006`

## Context

Prior to this decision, rectangular sketches could only be authored as four individual `line` entities (`SK-ENT-004`). Although four connected lines produce a valid profile in SOLIDWORKS, requiring agents to manually calculate and emit four coordinates with explicit endpoint chaining is verbose, error-prone (e.g. inverted winding or unclosed loop tolerance mismatches), and conflicts with standard CAD shape authoring where corner rectangles and center rectangles are primary primitives (spec §5.3.2 Tier 1, §5.7.4, §22.4.1).

## Decision

- **Add `corner_rectangle` and `center_rectangle` entities to Part Feature Graph IR:**
  - `corner_rectangle`:
    ```json
    {
      "type": "corner_rectangle",
      "corner1": [-50.0, -30.0],
      "corner2": [50.0, 30.0]
    }
    ```
    - `corner1`: `[x, y]` coordinates of one corner in sketch plane millimeters.
    - `corner2`: `[x, y]` coordinates of the opposite diagonal corner in sketch plane millimeters.
  - `center_rectangle`:
    ```json
    {
      "type": "center_rectangle",
      "center": [0.0, 0.0],
      "width": 100.0,
      "height": 60.0
    }
    ```
    - `center`: `[x, y]` coordinates of rectangle center in sketch plane millimeters.
    - `width`: Dimension along the sketch local x-axis in millimeters ($\ge 0.01$ mm).
    - `height`: Dimension along the sketch local y-axis in millimeters ($\ge 0.01$ mm).

- **Geometric Validation:**
  - Degeneracy check: for `corner_rectangle`, $|corner1.x - corner2.x| \ge 0.01$ mm and $|corner1.y - corner2.y| \ge 0.01$ mm. For `center_rectangle`, $width \ge 0.01$ mm and $height \ge 0.01$ mm.
  - Profiles for `extrude` and `cut_extrude` may consist of a single rectangle primitive, which inherently defines a closed, non-self-intersecting loop.

- **Canonical Lowering & Execution:**
  - A rectangle lowers deterministically into four counter-clockwise (CCW) oriented `line` entities:
    $$x_{min} = \min(x_1, x_2), \quad x_{max} = \max(x_1, x_2)$$
    $$y_{min} = \min(y_1, y_2), \quad y_{max} = \max(y_1, y_2)$$
    - Bottom edge: $(x_{min}, y_{min}) \to (x_{max}, y_{min})$
    - Right edge: $(x_{max}, y_{min}) \to (x_{max}, y_{max})$
    - Top edge: $(x_{max}, y_{max}) \to (x_{min}, y_{max})$
    - Left edge: $(x_{min}, y_{max}) \to (x_{min}, y_{min})$
  - In `ExecutionServer.Adapters`, `SketchAdapter.CreateSketch` natively executes or accepts lowered lines and rectangle entities with COM cleanup (`Marshal.ReleaseComObject`).

- **Face Transformation (Cap Faces):**
  - Sketches placed on `<extrude>.start_face` or `<extrude>.end_face` transform rectangle center/corners following the established coordinate mirroring rules of ADR-070.

## Rationale

1. **Agent Usability:** Agents writing Part Feature Graphs can specify rectangles concisely with either two diagonal points or center + dimensions, matching how mechanical engineers design mounting plates, pads, and pockets.
2. **Deterministic CCW Ordering:** Lowering to standard CCW line loops guarantees loop closure without numeric drift, preserving full compatibility with `cad-verification` Green's theorem area calculation and CAD extrusion routines.
3. **Spec Alignment:** Fulfills Tier 1 requirements for `SK-ENT-005` (Corner Rectangle) and `SK-ENT-006` (Center Rectangle).

## Consequences

- Agents can author rectangular extrusions and cuts with high clarity and minimal token overhead.
- Schema version bumps to v1.41.
