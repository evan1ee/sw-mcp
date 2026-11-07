# ADR-076: Mirror Feature in Part Feature Graph and Execution Server

## Context

The Part Feature Graph IR (spec 5.7, 22.5.2) supports solid base bodies (`extrude`), material removal (`cut_extrude`), linear feature patterns (`linear_pattern`, ADR-074), and circular feature patterns (`circular_pattern`, ADR-075). Bilateral and planar symmetry is one of the most fundamental principles in mechanical engineering: mounting brackets, chassis plates, flanges, enclosures, and linkage arms are predominantly designed with symmetry across a center plane. Authoring symmetrical features without a mirror feature forces duplicate sketch and cut definitions, doubling graph complexity and increasing error potential.

In the implementation checklist ([`patterns-mirrors.md`](../implementation/part-features/patterns-mirrors.md)), Mirror Feature (`PAT-MIR-001` through `PAT-MIR-004`) defines mirrored features (`seeds`), mirror plane (`plane`), and result merge (`merge`). In the SOLIDWORKS API (spec 8.9.11), mirror operations can be created via `IFeatureManager.InsertMirrorFeature2` or `CreateDefinition(swFmMirrorPattern)`.

## Decision

1. **Add `mirror` node to Part Feature Graph IR:**
   - Define schema in `schemas/part-feature-graph/features/mirror.json` and add `mirror` to the node union in `schemas/part-feature-graph/v0.json`.
   - Node properties:
     - `type`: `"mirror"`
     - `dependencies`: list of parent node IDs (must include the base body and every seed feature, plus the extrude if mirroring across a cap face).
     - `seeds`: array of feature node IDs being mirrored (e.g. `["cut_hole"]`).
     - `plane`: reference string identifying the mirror plane:
       - Standard datum planes: `"plane:front"`, `"plane:top"`, `"plane:right"`.
       - Or an extrude cap face: `"<extrude_id>.start_face"`, `"<extrude_id>.end_face"`.
     - `merge`: optional boolean (defaults to `true`).

2. **IPC Operation Contract (`feature.create`):**
   - Extend `schemas/ipc/ops/feature.create.json` to allow `type: "mirror"`.
   - Include `seeds`, `plane`, and `merge` parameters.

3. **Compiler Validation & Lowering:**
   - `cad-compiler` semantic validation verifies:
     - `seeds` reference valid existing `cut_extrude` features.
     - `plane` is a valid plane reference (`plane:front`, `plane:top`, `plane:right`, or `<extrude>.start_face`/`<extrude>.end_face`).
     - Every seed feature is declared in `dependencies`.
     - If `plane` is an extrude cap face, the extrude is declared in `dependencies`.
   - Lowers `mirror` into a `feature.create` operation dispatched to the backend.

4. **Verification Engine Closed-Form Geometry:**
   - `cad-verification` calculates closed-form mass properties:
     - Total volume: $V_{\text{actual}} = V_{\text{base}} - 2 \times \sum V_{\text{seed\_cut}}$.
     - Cylinder contracts: each seed cylinder is duplicated with its position reflected across the mirror plane:
       - Reflected across `plane:right` ($x=0$): $(x, y, z) \mapsto (-x, y, z)$, normal $(n_x, n_y, n_z) \mapsto (-n_x, n_y, n_z)$.
       - Reflected across `plane:top` ($y=0$): $(x, y, z) \mapsto (x, -y, z)$, normal $(n_x, n_y, n_z) \mapsto (n_x, -n_y, n_z)$.
       - Reflected across `plane:front` ($z=0$): $(x, y, z) \mapsto (x, y, -z)$, normal $(n_x, n_y, n_z) \mapsto (n_x, n_y, -n_z)$.
     - Bounding box: base body bounding box.
     - Feature verification expects `native_type: "MirrorPattern"`.

5. **Execution Server Adapter Implementation:**
   - In `ExecutionServer.Adapters`, `FeatureAdapter.CreateFeature` handles `FeatureCreateParamsType.Mirror`:
     - Clears active selection.
     - Selects the mirror plane or planar cap face with Mark 2.
     - Selects each seed feature with Mark 1.
     - Calls `doc.FeatureManager.InsertMirrorFeature2(false, false, false, false, 0)` or `CreateDefinition((int)swFeatureNameID_e.swFmMirrorPattern)` / `CreateFeature`.
     - Releases temporary COM references and manages tracking via `ComScope`.

## Status

Accepted.

## Consequences

- **Capabilities unlocked:** Bilateral symmetrical parts with mirrored cutouts or features can be authored concisely in Part Feature Graph IR.
- **Completes pattern/symmetry triad:** The three fundamental geometric duplication patterns—linear pattern (`PAT-LIN`), circular pattern (`PAT-CIR`), and mirror (`PAT-MIR`)—are fully supported.
- **Purity preserved:** Core packages remain purely functional and CAD-free; COM lifecycle is handled exclusively in C# add-in adapters.
