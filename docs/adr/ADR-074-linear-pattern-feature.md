# ADR-074: Linear Pattern Feature in Part Feature Graph and Execution Server

## Context

The Part Feature Graph IR (spec 5.7, 22.5.2) supports base bodies (`extrude`) and material removal (`cut_extrude`). While basic parts can be constructed with individual cut profiles, real-world mechanical parts frequently incorporate repeated feature patterns—such as bolt hole circles, vent slots, perforated plates, and heat sink fins. Authoring each hole individually in sketch profiles scales poorly, makes design intent implicit, and fails when patterns must be parametrically modified.

In the implementation checklist ([`patterns-mirrors.md`](../implementation/part-features/patterns-mirrors.md)), Linear Pattern (`PAT-LIN-001` through `PAT-LIN-004`) is the primary P1 pattern capability. In the SOLIDWORKS API (spec 8.9.11), `FeatureLinearPattern5` is obsolete, and official documentation mandates the typed feature data route: `FeatureManager.CreateDefinition(swFmLPattern)` returning `ILinearPatternFeatureData`.

## Decision

1. **Add `linear_pattern` node to Part Feature Graph IR:**
   - Define schema in `schemas/part-feature-graph/features/linear_pattern.json` and add `linear_pattern` to the node union in `schemas/part-feature-graph/v0.json`.
   - Node properties:
     - `type`: `"linear_pattern"`
     - `dependencies`: list of parent node IDs (must include the base body and every seed feature).
     - `seeds`: array of feature node IDs being patterned (e.g. `["cut_hole"]`).
     - `direction_1`: object defining primary pattern direction:
       - `direction`: a `GeometryRef` (e.g. `"plane:right"` for X direction, `"plane:top"` for Y direction, or reference plane/axis).
       - `spacing`: number $> 0$, distance between instances in millimetres.
       - `count`: integer $\ge 2$, total instance count including the seed.
       - `reverse`: optional boolean, defaults to `false`.
     - `direction_2`: optional object for 2D grid patterns with `direction`, `spacing`, `count`, `reverse`.

2. **IPC Operation Contract (`feature.create`):**
   - Extend `schemas/ipc/ops/feature.create.json` to allow `type: "linear_pattern"`.
   - Discriminate operation parameters so `linear_pattern` accepts `seeds`, `direction_1`, and optional `direction_2` without requiring a sketch profile or end condition.

3. **Compiler Validation & Lowering:**
   - `cad-compiler` semantic validation verifies:
     - `seeds` reference valid existing `cut_extrude` features.
     - `spacing >= 0.01` mm and `count >= 2`.
     - All patterned instances remain strictly inside the base body bounding volume.
   - Lowers `linear_pattern` into a `feature.create` operation dispatched to the backend.

4. **Verification Engine Closed-Form Geometry:**
   - `cad-verification` calculates closed-form mass properties:
     - Total instances $N = \text{count}_1 \times (\text{count}_2 \text{ if present else } 1)$.
     - Total volume: $V_{\text{actual}} = V_{\text{base}} - N \times V_{\text{seed\_cut}}$.
     - Cylinder contracts: each seed cylinder is replicated $N$ times.
     - Bounding box: unchanged from base extrude bounding box.

5. **Execution Server Adapter Implementation:**
   - In `ExecutionServer.Adapters`, `FeatureAdapter.CreateFeature` handles `FeatureCreateParamsType.LinearPattern`:
     - Looks up seed feature(s) via `FeatureLookup.FindById`.
     - Resolves direction plane or axis from the document.
     - Calls `doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmLPattern)` to obtain `ILinearPatternFeatureData`.
     - Populates `D1Axis`, `D1Spacing` (converted to meters), `D1TotalInstances`, `D1ReverseDirection`, `PatternFeatureArray = new object[] { seedFeature }`.
     - Invokes `doc.FeatureManager.CreateFeature(featData)` with strict COM lifecycle tracking via `ComScope`.

## Status

Accepted.

## Consequences

- **Capabilities unlocked:** Multi-hole plates, linear cut arrays, and repeated features can be authored declaratively in Part Feature Graph IR.
- **Purity preserved:** Core packages remain CAD-free and purely functional; side effects and COM manipulation remain confined to `ExecutionServer.Adapters`.
- **Zero COM leaks:** All temporary feature data and plane objects are released cleanly under Guideline G1.
