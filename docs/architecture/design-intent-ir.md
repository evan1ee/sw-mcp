# 4. Design Intent IR

> Specification v1.23, section 4. Index and section map: [specifications/README.md](../specifications/README.md).

## 4.1 Purpose

The Design Intent IR is an optional module (section 3.3). A task uses it only when it has engineering requirements to state or check. It represents *what* the part or product must do and how it is made and inspected, independent of *how* the model is built. If the modeling strategy changes, the intent does not. It holds three kinds of requirements:

- **Functional:** what features must do, e.g. bearing seat, sealing face, mounting interface, clearance to a mating part.
- **Manufacturing:** process, material, treatment, and process-specific inputs (parting line, gate, grain direction, edge break).
- **Inspection:** which requirements must be measured and reported.

## 4.2 Phasing

- **Minimum (4.3; schema in Phase 0, implemented in Phase 3, P2).** Requirements are stated, not computed. Each functional requirement has a short statement and a kind. When a drawing is made, the Drawing Intent IR (11.10) holds the dimensions, tolerances and GD&T that specify it. Drawings do not need a Design Intent IR. Without one, they use the fallbacks in 3.3 rule 4 **[Builder's call]**.
- **Full model (4.4–4.6, P3).** Constraints, parameters, relationships, a natural-language interface, and machine-checkable limits. The Drawing Intent specification can then be derived from the requirements and verified against them.

The minimum is a strict subset of the full model, so nothing is migrated later. Tolerance, datum, GD&T and geometry-reference types are defined once in a shared schema, which the Design Intent IR and Drawing Intent IR both use.

## 4.3 Design Intent IR — Minimum

| Field | Description |
| --- | --- |
| module, id, schema_version, units | Document header (3.4.5) |
| metadata | Part number, revision, author, timestamps. The title block reads these |
| process | `machined` \| `molded` \| `sheet_metal`. Selects the drawing profile (11.3) |
| material | Material name and grade. The title block reads it |
| treatment | Surface treatment or coating (e.g. "Anodize clear"). Roughness values belong in the Drawing Intent IR |
| manufacturing | Process-specific inputs: parting line, gate/ejector notes, grain direction, edge-break size, extra thread specs. Read from the model where possible (draft from Draft features, threads from Hole Wizard / cosmetic threads); the intent overrides the model **[Builder's call]** |
| functional_features | Named features that requirements apply to (`bearing_bore`, `base_face`). Feature Graph nodes declare which ones they realize (`realizes`, section 5) |
| requirements | Functional requirements, keyed by ID (3.4.1): kind (`fit`, `clearance`, `sealing`, `alignment`, `mounting`, `load`, `other`), `targets` (array of functional feature names), statement. Optional `limits` are reserved for P3 checks |
| inspection | Requirement IDs that must be inspected. Drawing Intent items that serve them get QA balloons (11.3) |

Example:

```json
{
  "module": "design_intent",
  "id": "BRK-001-DES",
  "schema_version": "0.1",
  "units": "mm",
  "metadata": { "part_number": "BRK-001", "revision": "A" },
  "process": "machined",
  "material": "AL 6061-T6",
  "treatment": "Anodize clear",
  "functional_features": ["base_face", "bearing_bore", "mount_holes"],
  "requirements": {
    "r1": { "kind": "fit", "targets": ["bearing_bore"],
            "statement": "Press fit for 6204 bearing outer ring" },
    "r2": { "kind": "alignment", "targets": ["bearing_bore", "base_face"],
            "statement": "Bearing axis square to mounting face" },
    "r3": { "kind": "mounting", "targets": ["mount_holes"],
            "statement": "Matches M6 pattern on frame plate" }
  },
  "inspection": ["r1", "r2", "r3"]
}
```

The Drawing Intent IR turns these into specifications. For example, `r1` becomes Ø47 H7 on the bore, and `r2` becomes a perpendicularity of the bore axis to datum A (example in 11.10).

## 4.4 Full Data Model (P3)

| Field | Description |
| --- | --- |
| parameters | Named design parameters |
| constraints | Engineering constraints |
| materials | Material definitions |
| manufacturing | Manufacturing requirements |
| relationships | Functional and geometric relationships |
| verification | Required verification criteria |

## 4.5 Constraint Types (P3)

- **Dimensional:** length, width, height, diameter, radius, thickness, distance, angle.
- **Geometric:** parallel, perpendicular, tangent, concentric, coincident, symmetric, equal.
- **Engineering:** min/max wall thickness, min edge distance, hole spacing, clearance, interference, min radius.
- **Manufacturing:** draft angle, mold opening direction, undercuts, min feature size, tool access, machining allowance.

Each constraint defines: id, type, target geometry or parameters, expected value or range, units, tolerance, verification method, severity.

## 4.6 Parameters

Parameters are explicit and reusable:

```json
{
  "parameters": {
    "housing_length": { "value": 80, "unit": "mm" },
    "wall_thickness": { "value": 1.5, "unit": "mm" },
    "draft_angle": { "value": 1, "unit": "deg" }
  }
}
```

Expressions and parameter dependencies come in a later schema version.
