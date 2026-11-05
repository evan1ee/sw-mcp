# 5.6 Assembly Graph IR (optional module)

> Specification v1.28, section 5.6. Index and section map: [specifications/README.md](../specifications/README.md).

## Purpose

The Assembly Graph IR describes how parts go together and move: component hierarchy, instances, mates, interfaces and motion relationships. Only tasks that involve assembly-level operations use it (3.3). It never contains part geometry. Each component points to a Part Feature Graph, which is either built by this system or read-only from an existing part.

## Structure

| Element | Fields |
| --- | --- |
| document | Document header (3.4.5), assembly name |
| components | Keyed by component ID (3.4.1): part (`DocumentRef` to a Part Feature Graph, `part:<id>`, or to a nested Assembly Graph, `assembly:<id>`; an existing part on disk is first read into the store as a read-only graph, 13.1), configuration, placement (`fixed`, `float`, or an initial transform), suppression |
| hierarchy | Subassemblies: nested Assembly Graph documents, each marked rigid or flexible |
| mates | Keyed by mate ID: type (standard: coincident, concentric, distance, angle, parallel, perpendicular, tangent, lock; mechanical: gear, rack-and-pinion, screw, cam, slot, hinge, limit distance/angle), two or more `targets` (component ID plus a `GeometryRef` resolved in that component's part graph, 3.4.2 rule 1, or an interface), alignment (aligned / anti-aligned), values |
| interfaces | Named connection points of a component (e.g. `piston.rod_end`), mapped to the part's geometry and optionally to Design Intent functional features. Mates may target interfaces instead of raw geometry, so they survive part edits better |
| motion | Drivers (motor, spring, force, gravity), limits and motion-study settings |

Example (excerpt):

```json
{
  "module": "assembly", "id": "injector", "schema_version": "0.1", "units": "mm",
  "components": {
    "housing": { "part": "part:injector_housing", "placement": "fixed" },
    "piston": { "part": "part:piston", "placement": "float" }
  },
  "mates": {
    "m1": { "type": "concentric",
      "targets": [ { "component": "housing", "ref": "bore_main.cylindrical_face" },
                   { "component": "piston", "ref": "body.cylindrical_face" } ] },
    "m2": { "type": "limit_distance", "min": 0, "max": 25,
      "targets": [ { "component": "housing", "ref": "bore_main.bottom_face" },
                   { "component": "piston", "ref": "body.front_face" } ] }
  }
}
```

## Rules

- Mate targets are geometry references resolved per component. The ambiguity rules of section 7 apply, and a mate whose target is ambiguous fails; it is never attached to a guessed face.
- Over-defined, conflicting or unsolved mates reported by SOLIDWORKS are API verification failures (10.2). They are never reported as success.
- Editing a part never edits mates. Mates that no longer resolve after a part change are reported (3.3 rule 5).
- Motion parameters such as spring force can come from the Design Intent IR. A spring's geometry belongs to its Part Feature Graph; its force is a motion element, not geometry.

## Phasing [Builder's call]

- **v0 (Phase 2):** components, hierarchy and standard mates. This reaches the reference implementation's assembly level as an IR. Until then, assemblies stay on the reference implementation (2.4), so no capability is lost.
- **Later (P3):** mechanical mates, interfaces and BOM.
- **Motion studies (P4):** need SOLIDWORKS Motion (a SOLIDWORKS Premium add-in license); this is an owner decision before it is scheduled.
