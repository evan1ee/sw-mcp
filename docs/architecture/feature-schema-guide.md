# 5.7 Part Feature Graph Schema Guide

> Specification v1.41, section 5.7. Index and section map: [specifications/README.md](../specifications/README.md).

Conventions every feature type's schema follows, so roughly 60 Tier 1 types (5.3.2) read as one language and the compiler's defaults are explicit. Each type has one schema file, `schemas/part-feature-graph/features/<type>.json`, with one minimal example of at most 400 tokens (12.3).

## 5.7.1 Graph document

```json
{
  "module": "part", "id": "bracket", "schema_version": "0.1", "units": "mm", "origin": "built",
  "nodes": {
    "sketch_base": { "type": "sketch", "plane": "plane:front",
      "entities": { "c1": { "type": "circle", "center": [0, 0], "diameter": 20 } },
      "dimensions": { "dia": { "type": "diameter", "entities": ["c1"], "value": 20 } } },
    "extrude_base": { "type": "extrude", "dependencies": ["sketch_base"], "profile": "sketch_base",
      "end_condition": { "type": "blind", "depth": 50 }, "realizes": ["base_face"] }
  }
}
```

| Node field | Description |
| --- | --- |
| *(key)* | Item ID (3.4.1) |
| `type` | Feature type from the registry, lower snake case (`extrude`, `cut_extrude`, `hole_wizard`, `sketch`). The tables in 5.3 use SOLIDWORKS-style display names; the registry name is their snake case (`HoleWizard` → `hole_wizard`). The registry says which types support Create and which Read (5.3) |
| `dependencies` | Set of node IDs this node needs, beyond those implied by its references. The compiler adds implied ones and rejects cycles |
| `parameters` | Only when the type has parameters that fit none of the shared objects below. Most parameters are named fields of the node |
| `suppressed` | `true` to build suppressed. Default `false` |
| `realizes` | Functional feature names (3.4.2 rule 1, ADR-024) |
| `display_name` | Optional, for reports only |
| `x_solidworks` | Backend-specific extension object (5.5). Never needed for a type to work; ignored by other backends |

**Order.** Nodes are built in topological order. Ties are broken by the node ID's sort order, so the same graph always builds the same feature order. A tie between two nodes that change a body would make geometry depend on how their IDs are spelled. The MVP's semantic rules prevent it for its one extrude and its cuts; [ADR-066](../adr/ADR-066-body-order-is-explicit.md) (Proposed) generalizes that.

## 5.7.2 Naming and values

- Fields and enum values are lower snake case. Booleans are named for the true case (`reverse`, `merge_result`).
- Lengths are in the document's `units` and angles in degrees (3.4.3). Counts are integers.
- A parameter that an agent or a drawing can refer to is a named field. Its `ParamRef` is `<node_id>.<field>` (`bore_1.diameter`), and for nested objects `<node_id>.<object>.<field>` (`extrude_base.end_condition.depth`). Sketch dimensions are `<sketch_id>.<dimension_id>` (`sketch_bore.x`). The grammar in 3.4.2 and the schema's `ParamRef` accept two segments only, so the nested form cannot validate yet: register K23.
- Parameter names and role names (5.7.5) are disjoint per type (3.4.2 rule 2).

## 5.7.3 Shared objects

| Object | Fields | Used by |
| --- | --- | --- |
| `end_condition` | `type` (`blind`, `through_all`, `through_all_both`, `up_to_next`, `up_to_surface`, `offset_from_surface`, `mid_plane`), `depth`, `target` (`GeometryRef`), `offset`, `reverse`, `draft` (`{angle, outward}`) | Extrude, cut, boss, rib |
| `end_condition_2` | Same, for the second direction | Same |
| `thin` | `thickness`, `type` (`one_side`, `mid_plane`, `two_side`), `thickness_2` | Thin extrude and revolve |
| `pattern` | `seeds` (node IDs), `direction` and `direction_2` (`GeometryRef`), `spacing`, `count`, `skip` (instance indices). A linear pattern's `spacing` is a length, and a circular pattern's an angle with `direction` as its axis | Linear and circular patterns. A mirror takes `seeds` and a `plane` (22.5.2, Proposed) |
| `hole_spec` | `standard` (`iso`), `type` (`simple`, `counterbore`, `countersink`, `tapped`), `size` (`M6`), `fit` (`close`, `normal`, `loose`), `depth` (`end_condition`), `thread_depth`, `cosmetic_thread` | Hole Wizard |
| `sheet_metal` | `thickness`, `bend_radius`, `k_factor` or `bend_table`, `relief` | Sheet metal parameters and features |

## 5.7.4 Sketches

| Field | Description |
| --- | --- |
| `plane` | `GeometryRef`: a standard plane (`plane:front`), a reference-plane node, or a planar face by role |
| `entities` | Keyed by entity ID. `line` (`start`, `end`), `circle` (`center`, `diameter`), `arc` (`center`, `start`, `end`, `direction`: `ccw` or `cw`), `corner_rectangle` (`corner1`, `corner2`), `center_rectangle` (`center`, `width`, `height`), `point`, `slot` (stored as lines and arcs plus an entity group), `spline` (Read only in Tier 1). `construction: true` marks construction geometry. Coordinates are 2D sketch coordinates in the document's units |
| `relations` | Keyed by relation ID: `type` (`coincident`, `horizontal`, `vertical`, `parallel`, `perpendicular`, `tangent`, `concentric`, `equal`, `fix`, …) and `entities`. A point of an entity is `<entity>.start`, `<entity>.end` or `<entity>.center` |
| `dimensions` | Keyed by dimension ID: `type` (`distance`, `horizontal`, `vertical`, `diameter`, `radius`, `angle`), `entities` and `value`. Each is a driving parameter (`<sketch_id>.<dimension_id>`) |

- The IR states final geometry, never editing steps (5.3.1).
- Sketch axes on each standard plane follow SOLIDWORKS's own sketch transform. The first live spike (2026-11-05, SOLIDWORKS 2025 revision 33.0.0, [record](../superpowers/review/2026-11-05-part-chain-spike.md)) recorded them, found with `ISketch.ModelToSketchTransform.Inverse()` applied to unit points:

  | Plane (role) | Sketch +x | Sketch +y | Normal (x cross y) | Blind extrude goes | Default blind cut goes | Blind cut with `Dir=true` goes |
  | --- | --- | --- | --- | --- | --- | --- |
  | `plane:front` | model +X | model +Y | +Z | +Z | -Z | +Z |
  | `plane:top` | model +X | model -Z | +Y | +Y | -Y | +Y |
  | `plane:right` | model -Z | model +Y | +X | +X | -X | +X |

- **Standard planes [Builder's call].** The document's first three `RefPlane` features are Front, Top and Right, in that order (5.3.6). Their names are localized, so the order is the only key. A plane's normal is read by applying `IRefPlane.Transform` to the point (0, 0, 1) and subtracting the image of (0, 0, 0). It gives Front (0, 0, 1), Top (0, 1, 0) and Right (1, 0, 0). The adapter checks the normal against the role and fails clearly on a mismatch, so a template with reordered or rotated planes is caught at once.
- **Blind cut direction [Builder's call].** A blind `cut_extrude` goes the opposite way to a blind `extrude` by default: against the normal, so on a plate's own plane it finds nothing to cut and `FeatureCut4` returns null. The flip argument (`Flip=true`) selects which side of the profile is removed and does not help. The compiler's plan and the adapter must therefore pass the cut's direction argument `Dir=true`, which sends the blind cut along the normal, into the body. `through_all_both` is unaffected and works whichever way the normal points.
- **Selection [Builder's call].** A plane or sketch is selected with `IFeature.Select2(false, 0)`; entities (faces, edges, sketch segments) with `IEntity.Select4`. `SelectByID2` stays banned (8.3 rule 11).
- **Units [Builder's call].** The API takes metres whatever the document units are. The spike built the same plate in a millimetre and in an inch document with identical geometry. Mass properties are read with `IMassProperty.UseSystemUnits = true`; with `false` the values follow neither metres nor the document's linear unit.

- **Sketch on a face [ADR-070, spikes 2026-11-06 & 2026-11-07].** `plane` may be `<extrude_id>.end_face` or `<extrude_id>.start_face` (not `side_faces`, edges or faces of a cut). The compiler states the face's outward normal and offset; the add-in finds the extrude's planar face with that normal and offset, selects it with `Entity.Select4`, and opens the sketch (live record: [face spike](../superpowers/review/2026-11-06-face-sketch-spike.md)). Across all three standard base planes (`plane:front`, `plane:top`, `plane:right`), SOLIDWORKS 2025 gives these sketch frames (closing K29):

  | Base plane | Face | Sketch origin | Sketch +x | Sketch +y | Sketch normal |
  | --- | --- | --- | --- | --- | --- |
  | `plane:front` | `end_face` | `(0, 0, depth)` | `+X (1, 0, 0)` | `+Y (0, 1, 0)` | `+Z (0, 0, 1)` |
  | `plane:front` | `start_face` | `(0, 0, 0)` | `-X (-1, 0, 0)` | `+Y (0, 1, 0)` | `-Z (0, 0, -1)` |
  | `plane:top` | `end_face` | `(0, depth, 0)` | `+X (1, 0, 0)` | `-Z (0, 0, -1)` | `+Y (0, 1, 0)` |
  | `plane:top` | `start_face` | `(0, 0, 0)` | `+X (1, 0, 0)` | `+Z (0, 0, 1)` | `-Y (0, -1, 0)` |
  | `plane:right` | `end_face` | `(depth, 0, 0)` | `-Z (0, 0, -1)` | `+Y (0, 1, 0)` | `+X (1, 0, 0)` |
  | `plane:right` | `start_face` | `(0, 0, 0)` | `+Z (0, 0, 1)` | `+Y (0, 1, 0)` | `-X (-1, 0, 0)` |

  The rule the compiler uses: an `end_face` has the base plane's axes, with the origin moved by `depth` along the base normal; a `start_face` reverses the normal and mirrors `x` on vertical cap faces (`plane:front` and `plane:right`, where global `+Y` stays the sketch `+y` axis) and mirrors `y` on horizontal cap faces (`plane:top`, where global `+X` stays the sketch `+x` axis). The add-in compares the opened sketch's axes with the stated ones and fails the operation (`REF_SIGNATURE_MISMATCH`) on a mismatch.
- **Blind cut from a face [ADR-070].** A blind `cut_extrude` whose sketch is on a face goes into the body with `Flip=false` and `Dir=false`. `Dir=true` finds nothing and `Flip=true` removes the material outside the profile. A cut from an origin plane keeps `Dir=true` (above).

## 5.7.5 Roles

Each type's schema lists the roles it defines (11.1, 3.4.2): the role name, the entity kind, and the rule that finds it from the gathered facts (ADR-049). For example:
- **Extrude:** `start_face` (planar, on the profile's plane), `end_face` (planar, parallel to it at the end condition), `side_faces` (a set).
- **Hole Wizard:** `cylindrical_face`, `axis`, `counterbore_face`.
- **Revolve:** `faces_by_axial_order` (a list ordered along the axis).

A role that is a set or a list can be referred to as a whole where the field takes a set, otherwise only with an index (`extrude_base.side_faces.0`, not yet accepted by the schema's `GeometryRef`: register K23), and only where the type defines a stable order. A role that matches more than one entity when one is expected fails with `REF_AMBIGUOUS` (7.4).

## 5.7.6 Defaults

- Optional fields may be omitted (12.3 rule 5). The value the compiler uses for each is in `packages/cad-compiler/defaults/<compiler version>.json`, one table per feature type, versioned with the compiler.
- Schemas may show a default in `description` for agents, but never use JSON Schema's `default` keyword for meaning, so validation never fills values silently.
- The compiler records every default it applied in the plan's `defaults` (6.5.3). A change to the defaults table is a compiler version change and appears in the plan's provenance.
