# ADR-071: Sketch arc primitives defined by center, start, end, and direction

- **Status:** Accepted (owner, 2026-11-07, in the 3D part feature expansion plan)
- **Source:** [plan](../superpowers/plans/2026-11-07-sketch-arcs.md); specification v1.40, section 22.4.1; checklist `SK-ENT-013`, `SK-ENT-016`

## Context

The Part Chain MVP supported only `line` and `circle` sketch entities. This prevented agents from creating parts with rounded corners, slots, rounded tabs, or curved cutouts without 3D edge fillets. 3D edge fillets and chamfers (`SHP-FIL`, `SHP-CHM`) require edge semantic references, which are blocked by open decisions K23 (multi-segment reference grammar) and K28 (persistent entity references). Adding 2D sketch arcs introduces curved geometry into the Part Chain immediately without any external blockers.

## Decision

- **Add `arc` entity to Part Feature Graph IR:**
  ```json
  {
    "type": "arc",
    "center": [0.0, 0.0],
    "start": [10.0, 0.0],
    "end": [0.0, 10.0],
    "direction": "ccw"
  }
  ```
  - `center`: `[x, y]` center coordinates in sketch plane millimeters.
  - `start`: `[x, y]` starting point coordinates in sketch plane millimeters.
  - `end`: `[x, y]` ending point coordinates in sketch plane millimeters.
  - `direction`: `"ccw"` (counter-clockwise) or `"cw"` (clockwise).
- **Geometric Validation:**
  - Radius consistency: $\|start - center\| == \|end - center\|$ within numerical quantum ($10^{-6}$ mm).
  - Minimum radius: $\|start - center\| \ge 0.01$ mm.
  - Distinct points: $start \ne end$. Full 360° circular loops must use `type: "circle"`.
- **Closed Loop Profiles:**
  - Profiles for `extrude` and `cut_extrude` may consist of a single closed loop formed by any combination of connected `line` and `arc` entities where sequential endpoints connect within $10^{-6}$ mm.
- **SOLIDWORKS Adapter Mapping:**
  - In `ExecutionServer.Adapters`, `SketchAdapter.CreateSketch` calls `ISketchManager.CreateArc(xc, yc, 0, xp1, yp1, 0, xp2, yp2, 0, dir)` where `dir = 1` for `ccw` and `dir = -1` for `cw`.
  - The returned COM pointer (`ISketchSegment` / `ISketchArc`) is released immediately via `Marshal.ReleaseComObject` (Guideline G1).

## Rationale

SOLIDWORKS' native `CreateArc` takes center, start, end, and direction (`+1` for CCW, `-1` for CW). Standardizing the IR on center, start, end, and direction aligns 1:1 with native CAD execution, eliminates trigonometric ambiguity in angle conversions, and ensures deterministic geometric representation.

## Consequences

- Parts with rounded tabs, slots, and filleted contours can be authored and built directly in 2D sketches.
- `cad-verification` calculates exact expected cross-sectional areas and 3D bounding boxes spanning arc extrema.
- Spec version bumps to v1.40.
