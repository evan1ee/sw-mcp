# 5.7 Part Feature Graph Schema Guide

> Specification v1.29, section 5.7. Index and section map: [specifications/README.md](../specifications/README.md).

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

**Order.** Nodes are built in topological order. Ties are broken by the node ID's sort order, so the same graph always builds the same feature order.

## 5.7.2 Naming and values

- Fields and enum values are lower snake case. Booleans are named for the true case (`reverse`, `merge_result`).
- Lengths are in the document's `units` and angles in degrees (3.4.3). Counts are integers.
- A parameter that an agent or a drawing can refer to is a named field. Its `ParamRef` is `<node_id>.<field>` (`extrude_base.depth`), and for nested objects `<node_id>.<object>.<field>` (`extrude_base.end_condition.depth`). Sketch dimensions are `<sketch_id>.<dimension_id>` (`sketch_bore.x`).
- Parameter names and role names (5.7.5) are disjoint per type (3.4.2 rule 2).

## 5.7.3 Shared objects

| Object | Fields | Used by |
| --- | --- | --- |
| `end_condition` | `type` (`blind`, `through_all`, `through_all_both`, `up_to_next`, `up_to_surface`, `offset_from_surface`, `mid_plane`), `depth`, `target` (`GeometryRef`), `offset`, `reverse`, `draft` (`{angle, outward}`) | Extrude, cut, boss, rib |
| `end_condition_2` | Same, for the second direction | Same |
| `thin` | `thickness`, `type` (`one_side`, `mid_plane`, `two_side`), `thickness_2` | Thin extrude and revolve |
| `pattern` | `seeds` (node IDs), `direction` and `direction_2` (`GeometryRef`), `spacing`, `count`, `skip` (instance indices) | Linear, circular and mirror patterns |
| `hole_spec` | `standard` (`iso`), `type` (`simple`, `counterbore`, `countersink`, `tapped`), `size` (`M6`), `fit` (`close`, `normal`, `loose`), `depth` (`end_condition`), `thread_depth`, `cosmetic_thread` | Hole Wizard |
| `sheet_metal` | `thickness`, `bend_radius`, `k_factor` or `bend_table`, `relief` | Sheet metal parameters and features |

## 5.7.4 Sketches

| Field | Description |
| --- | --- |
| `plane` | `GeometryRef`: a standard plane (`plane:front`), a reference-plane node, or a planar face by role |
| `entities` | Keyed by entity ID. `line` (`start`, `end`), `circle` (`center`, `diameter`), `arc` (`center`, `start`, `end`, `direction`: `ccw` or `cw`), `point`, `rectangle` and `slot` (stored as their lines and arcs plus an entity group), `spline` (Read only in Tier 1). `construction: true` marks construction geometry. Coordinates are 2D sketch coordinates in the document's units |
| `relations` | Keyed by relation ID: `type` (`coincident`, `horizontal`, `vertical`, `parallel`, `perpendicular`, `tangent`, `concentric`, `equal`, `fix`, …) and `entities`. A point of an entity is `<entity>.start`, `<entity>.end` or `<entity>.center` |
| `dimensions` | Keyed by dimension ID: `type` (`distance`, `horizontal`, `vertical`, `diameter`, `radius`, `angle`), `entities` and `value`. Each is a driving parameter (`<sketch_id>.<dimension_id>`) |

- The IR states final geometry, never editing steps (5.3.1).
- Sketch axes on each standard plane follow SOLIDWORKS's own sketch transform. Phase 0 records the exact axis directions per plane from the live API, and this guide is updated with them before Phase 1c.

## 5.7.5 Roles

Each type's schema lists the roles it defines (11.1, 3.4.2): the role name, the entity kind, and the rule that finds it from the gathered facts (ADR-049). For example:
- **Extrude:** `start_face` (planar, on the profile's plane), `end_face` (planar, parallel to it at the end condition), `side_faces` (a set).
- **Hole Wizard:** `cylindrical_face`, `axis`, `counterbore_face`.
- **Revolve:** `faces_by_axial_order` (a list ordered along the axis).

A role that is a set or a list can be referred to only with an index (`extrude_base.side_faces.0`), and only where the type defines a stable order. A role that matches more than one entity when one is expected fails with `REF_AMBIGUOUS` (7.4).

## 5.7.6 Defaults

- Optional fields may be omitted (12.3 rule 5). The value the compiler uses for each is in `packages/cad-compiler/defaults/<compiler version>.json`, one table per feature type, versioned with the compiler.
- Schemas may show a default in `description` for agents, but never use JSON Schema's `default` keyword for meaning, so validation never fills values silently.
- The compiler records every default it applied in the plan's `defaults` (6.5.3). A change to the defaults table is a compiler version change and appears in the plan's provenance.
