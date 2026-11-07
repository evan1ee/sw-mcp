# ADR-075: Circular Pattern Feature in Part Feature Graph and Execution Server

## Context

The Part Feature Graph IR (spec 5.7, 22.5.2) supports base bodies (`extrude`), material removal (`cut_extrude`), and linear feature patterns (`linear_pattern`, ADR-074). Rotational symmetry is equally fundamental to mechanical CAD design: bolt circles on flanges, radial cooling holes, wheel lug patterns, turbine and impeller vanes, and clockwork components all require circular patterns.

In the implementation checklist ([`patterns-mirrors.md`](../implementation/part-features/patterns-mirrors.md)), Circular Pattern (`PAT-CIR-001` through `PAT-CIR-005`) defines seed features (`seeds`), axis (`axis`), angular spacing (`spacing`), instance count (`count`), and equal spacing (`equal_spacing`). In the SOLIDWORKS API (spec 8.9.11), `FeatureCircularPattern5` is obsolete, and official documentation mandates the typed feature data route: `FeatureManager.CreateDefinition(swFmCirPattern)` returning `ICircularPatternFeatureData`.

## Decision

1. **Add `circular_pattern` node to Part Feature Graph IR:**
   - Define schema in `schemas/part-feature-graph/features/circular_pattern.json` and add `circular_pattern` to the node union in `schemas/part-feature-graph/v0.json`.
   - Node properties:
     - `type`: `"circular_pattern"`
     - `dependencies`: list of parent node IDs (must include the base body and every seed feature).
     - `seeds`: array of feature node IDs being patterned (e.g. `["cut_hole"]`).
     - `axis`: a `GeometryRef` or reference string identifying the rotational axis (e.g. `"plane:front"` for normal to Front plane passing through origin, an axis reference, or a cylindrical body/face reference).
     - `count`: integer $\ge 2$, total instance count including the seed.
     - `spacing`: number in degrees ($0 < \text{spacing} \le 360.0$). When `equal_spacing: true`, represents the total angle (typically 360.0°); when `false`, represents the step angle between instances.
     - `equal_spacing`: optional boolean (defaults to `true`).
     - `reverse`: optional boolean (defaults to `false`).

2. **IPC Operation Contract (`feature.create`):**
   - Extend `schemas/ipc/ops/feature.create.json` to allow `type: "circular_pattern"`.
   - Include `seeds`, `axis`, `count`, `spacing`, `equal_spacing`, and `reverse` parameters.

3. **Compiler Validation & Lowering:**
   - `cad-compiler` semantic validation verifies:
     - `seeds` reference valid existing `cut_extrude` features.
     - `count >= 2`.
     - `0.001 <= spacing <= 360.0`.
     - `axis` is a valid reference.
   - Lowers `circular_pattern` into a `feature.create` operation dispatched to the backend.

4. **Verification Engine Closed-Form Geometry:**
   - `cad-verification` calculates closed-form mass properties:
     - Total instances $N = \text{count}$.
     - Total volume: $V_{\text{actual}} = V_{\text{base}} - N \times V_{\text{seed\_cut}}$.
     - Cylinder contracts: each seed cylinder is replicated $N$ times rotated around the axis.
     - Bounding box: base body bounding box.
     - Feature verification expects `native_type: "CirPattern"`.

5. **Execution Server Adapter Implementation:**
   - In `ExecutionServer.Adapters`, `FeatureAdapter.CreateFeature` handles `FeatureCreateParamsType.CircularPattern`:
     - Selects seed features with Mark 4.
     - Resolves the rotational axis entity (cylindrical face or circular edge coaxial with the axis) and selects it with Mark 1.
     - Calls `doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmCirPattern)` to obtain `ICircularPatternFeatureData`.
     - Sets `TotalInstances = (int)p.Count`, `EqualSpacing = p.EqualSpacing ?? true`, `Spacing = GeometryMath.DegToRad(p.Spacing)`, `ReverseDirection = p.Reverse ?? false`.
     - Invokes `doc.FeatureManager.CreateFeature(featData)` with strict COM lifecycle tracking via `ComScope`.

## Status

Accepted.

## Consequences

- **Capabilities unlocked:** Flange bolt circles, radial vent holes, and rotational feature patterns can be authored declaratively in Part Feature Graph IR.
- **Purity preserved:** Core packages remain purely functional and CAD-free; COM lifecycle is handled exclusively in C# add-in adapters.
- **Robust axis handling:** Coaxial cylindrical faces and circular edges provide reliable rotational axes in SOLIDWORKS without COM leaks.
