# 11.10 Drawing Intent IR (P0)

> Specification v1.23, section 11.10. Index and section map: [specifications/README.md](../specifications/README.md).

The Drawing Intent IR is optional for tasks in general and required for every drawing task (section 3.3). It says what the drawing specifies: dimensions, tolerances, GD&T, datums and surface finish. Material, process, treatment and part metadata come from the Design Intent IR when one is attached (4.3). Otherwise they come from the part's SOLIDWORKS material and custom properties, overridden by `context` (3.3 rule 4). With PMI output (P2, 11.4), the same Drawing Intent IR is emitted as 3D annotations in the part.

| Field | Description |
| --- | --- |
| module, id, schema_version, units | Document header (3.4.5) |
| documents | `DocumentRef` (3.4.2) to the Part Feature Graph (or, at the reference level, Assembly Graph) this drawing documents. `ParamRef` and `GeometryRef` values in this document resolve in it |
| design_intent | Optional. `DocumentRef` to the Design Intent IR this drawing specifies, e.g. `design_intent:BRK-001-DES@2` |
| context | Optional, and only allowed when no Design Intent IR is attached: `process` (selects the profile), `material`, `treatment`, `metadata` (part number, revision). Each value overrides the part's own property |
| configuration | SOLIDWORKS configuration the drawing views reference. Defaults to the active configuration; required when the part has more than one **[Builder's call]** |
| general_tolerance | Default class `m` (11.2) **[Builder's call]**. The designation written is `ISO 2768-m` with ISO 22081 (owner decision, ADR-050). Overridable per part |
| surface_finish | `general` roughness (the "unless noted" value, e.g. Ra 1.6) and per-face `exceptions`, keyed by ID: `target` geometry plus value (e.g. Ra 0.8). The machined profile places a symbol on each exception |
| datums | Datum features keyed by label (A, B, C; 3.4.1), their target geometry (`ref`) and `applies_to` (`surface` or `feature_of_size`, e.g. a bore's axis) |
| critical_dimensions | Dimensions that must appear explicitly, keyed by ID, each referencing a feature parameter or geometry reference, with optional tolerance, optional `requirement` it serves, and optional `inspect: true` |
| gdt | GD&T callouts (ISO 1101), keyed by ID: characteristic, tolerance, datum references, target geometry, `applies_to` (`surface`, the integral surface, or `feature_of_size`, its derived axis or median plane, in which case the frame attaches to the size dimension), optional `requirement` and optional `inspect` |
| scheme_overrides | Authored dimension scheme entries: changes an engineer or agent made to derived entries, and entries they added. Applied on top of the derived scheme to form the Resolved Scheme (11.10.1) |

QA balloons go on every item whose `requirement` is listed in the Design Intent `inspection` (4.3). Without a Design Intent IR, they go on items marked `inspect: true`.

Without a Design Intent IR, the same drawing is written with `context` in place of `design_intent`, and `inspect: true` in place of `requirement`:

```json
"context": { "process": "machined", "material": "AL 6061-T6", "treatment": "Anodize clear",
             "metadata": { "part_number": "BRK-001", "revision": "A" } }
```

Example with a Design Intent IR attached (specifying the example in 4.3):

```json
{
  "module": "drawing_intent",
  "id": "BRK-001-DI",
  "schema_version": "0.1",
  "units": "mm",
  "documents": "part:bracket@4",
  "design_intent": "design_intent:BRK-001-DES@2",
  "configuration": "Default",
  "general_tolerance": "ISO 2768-m",
  "surface_finish": {
    "general": { "ra": 1.6 },
    "exceptions": { "finish_bore": { "target": "bore_1.cylindrical_face", "ra": 0.8, "requirement": "r1" } }
  },
  "datums": {
    "A": { "ref": "base_extrude.bottom_face", "applies_to": "surface" },
    "B": { "ref": "bore_1.cylindrical_face", "applies_to": "feature_of_size" }
  },
  "critical_dimensions": {
    "bore_dia": { "param": "bore_1.diameter",
                  "tolerance": { "type": "fit", "value": "H7" }, "requirement": "r1" },
    "hole_spacing": { "param": "hole_pattern.spacing",
                      "tolerance": { "type": "symmetric", "value": 0.05 }, "requirement": "r3" }
  },
  "gdt": {
    "perp_bore": { "characteristic": "perpendicularity", "tolerance": 0.02,
                   "target": "bore_1.cylindrical_face", "applies_to": "feature_of_size",
                   "datums": ["A"], "requirement": "r2" }
  }
}
```

Dimensions not listed as critical take the general tolerance. In the example, the perpendicularity applies to the bore's axis. Its frame therefore attaches to the Ø dimension, not to the cylindrical surface. The two attachments mean different things under ISO 1101, so the intent must state which one is meant.

## 11.10.1 Dimension Scheme

The dimension scheme says *what* is dimensioned. The Drawing Layout IR says *where* (11.11). It has two parts, kept apart like a manifest and its lock file (ADR-023) **[Builder's call]**:

- **Authored:** `critical_dimensions` and `scheme_overrides` in the Drawing Intent IR. Engineers and agents write these. Changing them is a new Drawing Intent revision.
- **Resolved Scheme:** the full set of entries the drawing shows, produced by the pipeline: cleanup and gap filling (11.4) turn the inserted model items into derived entries, then the overrides are applied on top. It is a derived artifact owned by the pipeline, not an IR module. It is keyed by the Drawing Intent revision, the part's revision (13.1) and the pipeline version, and stored with the drawing's other state (13.1). Regenerating it never changes the Drawing Intent revision, and agents never send it back.

Completeness, duplicate and critical-dimension checks (D4–D6) compare the read-back drawing against the Resolved Scheme. `get_drawing_layout` and `get_drawing_report` show it in summary form; the full scheme is paginated.

Entry IDs must stay stable across regeneration, because Layout annotations and overrides refer to them. A derived entry's ID is computed from its `kind`, `covers`, `measures` and `source`, never from insertion order, by the rule in 3.4.4 **[Builder's call]**.

| Field | Description |
| --- | --- |
| *(key)* | Stable entry ID (3.4.4). Layout annotations reference it |
| kind | `linear`, `diameter`, `radius`, `angular`, `ordinate`, `hole_callout`, `thread_callout`, `chamfer`, `note`, `table_row` |
| covers | The driving parameters it covers, as `ParamRef`s (3.4.2). On hand-modelled parts these are the read graph's parameters, converted from `swdim:` full names at intake |
| measures | Geometry it measures (geometry references), and the datum or origin for location dimensions |
| source | `model_item` (inserted), `dimxpert`, `reference` (driven dimension the pipeline added), `authored` |
| tolerance | `general`, an explicit tolerance, or `{ "critical": "<id>" }` when the tolerance comes from that `critical_dimensions` entry |
| status | `shown`, `hidden` (with reason: `duplicate`, `non_functional`, `replaced_by:<id>`), `omitted` (with reason: `derived`, `reference`) |
| auxiliary | `true` for an auxiliary dimension (ISO 129-1): shown in parentheses, untoleranced, not inspected, and allowed to close a chain. Default `false`; a functional dimension is never auxiliary |
| origin | In the Resolved Scheme: `authored` (comes from a `scheme_overrides` entry) or `derived` (regenerated when the model changes) |

Example Resolved Scheme entries:

```json
"entries": {
  "ds_bore_1_diameter_b41219": { "kind": "diameter", "covers": ["bore_1.diameter"],
    "source": "model_item", "tolerance": { "critical": "bore_dia" },
    "status": "shown", "origin": "derived" },
  "ds_sketch_bore_x_4556c0": { "kind": "linear", "covers": ["sketch_bore.x"],
    "measures": { "from": "plane:right", "to": "bore_1.axis" },
    "source": "reference", "tolerance": "general",
    "status": "shown", "origin": "derived" },
  "ds_sketch_bore_x_be93d5": { "kind": "linear", "covers": ["sketch_bore.x"],
    "source": "model_item", "status": "hidden",
    "reason": "replaced_by:ds_sketch_bore_x_4556c0", "origin": "derived" }
}
```

An engineer can change any derived entry, for example to hide a dimension or choose a different datum, through `update_drawing_intent`. The change is stored as a `scheme_overrides` entry with the same ID, appears in the Resolved Scheme as `authored`, and is kept when the scheme is regenerated. If an override no longer resolves after a model change, it is reported, never dropped silently **[Builder's call]**.
