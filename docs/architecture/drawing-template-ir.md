# 11.12 Drawing Template IR

> Specification v1.35, section 11.12. Index and section map: [specifications/README.md](../specifications/README.md).

## Purpose

The Drawing Template IR defines a CAD-neutral, structured specification of a drawing sheet format: paper size, orientation, border margins, title block zones, static text, attribute links, and revision table placement.

Today, SOLIDWORKS drawing sheet formats can only exist as binary `.slddrt` files supplied by hand. Because the core never parses binary CAD files (13.3.4), it cannot know where the border or title block fields are located until SOLIDWORKS reports them, leaving open register item **K3** and forcing heuristic assumptions. Drawing Template IR follows the IR-first principle (1.3): the sheet format itself is pure data from which SOLIDWORKS formats can later be generated (ADR-055).

Generating `.slddrt` files or drawing sheet formats in SOLIDWORKS is not built in this increment and is tracked in open register item **K7** ([open-decisions.md](../specifications/open-decisions.md)) **[Builder's call]**.

## Structure

One document defines one sheet format: one paper size and orientation. Continuation sheets that use a different size or format use a separate `drawing_template` document.

| Element | Fields |
| --- | --- |
| Header | `module: "drawing_template"`, `id` (`DocumentId`), `schema_version: "0.1"`, `units: "mm"` (always), optional `revision`, optional `display_name` |
| `paper` | `size` (`A4`, `A3`, `A2`, `A1`, `A0`), `orientation` (`portrait`, `landscape`) |
| `border` | `margins` (`left`, `right`, `top`, `bottom` in mm, each positive), optional `line_width` (positive) |
| `title_block` | `zones`: rectangles keyed by item ID that together make the block (D7 keeps views out of them). `lines`: optional keyed line segments (`from`, `to`, optional `line_width`) |
| `texts` | Static text entries, keyed by item ID: `text` (min length 1), `box` (Rect), `height` (positive mm), optional `align` (`left`, `center`, `right`) |
| `fields` | Attribute link fields, keyed by field name (matching 13.3.4 and D8): `source` (ordered candidate list), optional `required` (boolean), optional `label`, `box` (Rect), `height` (positive mm), optional `align` |
| `revision_table` | Optional: `box` (Rect). Its presence indicates sheets using this format carry a revision table |

Coordinates are sheet millimetres from the lower-left corner `[0, 0]`, matching 11.11. Rectangles use `{ "min": [x1, y1], "max": [x2, y2] }`, matching the Drawing Geometry Snapshot (11.5.1), so template zones map directly onto snapshot title block exclusion zones for check D7.

## Source Grammar

Field sources (`fields.<name>.source`) define an ordered list of candidate locations from which the field value is resolved. The first candidate present wins (late-bound lookup):

- `part_property:<name>`: custom property on the referenced part model.
- `drawing_property:<name>`: custom property on the drawing document.
- `part_material`: resolved material of the referenced part.
- `design_intent:<path>`: dotted path into the Design Intent IR document (e.g. `design_intent:metadata.part_number`).
- `drawing_intent:<path>`: dotted path into the Drawing Intent IR document.
- `sheet:scale`, `sheet:projection`, `sheet:units`: sheet-level properties (these values belong to the sheet, not the part).

Candidate sources must follow ownership order (3.3 rule 4): `design_intent:` (rank 0), then `drawing_intent:` (rank 1), followed by part/drawing sources (rank 2). `sheet:` sources stand alone in the candidate list **[Builder's call]**.

## Example

```json
{
  "module": "drawing_template",
  "id": "ACME-A3",
  "schema_version": "0.1",
  "units": "mm",
  "paper": {
    "size": "A3",
    "orientation": "landscape"
  },
  "border": {
    "margins": {
      "left": 20.0,
      "right": 10.0,
      "top": 10.0,
      "bottom": 10.0
    },
    "line_width": 0.5
  },
  "title_block": {
    "zones": {
      "main": {
        "min": [230.0, 10.0],
        "max": [410.0, 60.0]
      }
    },
    "lines": {
      "top_divider": {
        "from": [230.0, 60.0],
        "to": [410.0, 60.0]
      }
    }
  },
  "texts": {
    "company": {
      "text": "ACME Industries",
      "box": {
        "min": [232.0, 50.0],
        "max": [300.0, 58.0]
      },
      "height": 5.0,
      "align": "left"
    }
  },
  "fields": {
    "part_number": {
      "label": "Part No.",
      "source": [
        "design_intent:metadata.part_number",
        "part_property:PartNo"
      ],
      "box": {
        "min": [232.0, 40.0],
        "max": [300.0, 48.0]
      },
      "height": 3.5,
      "align": "left"
    },
    "revision": {
      "source": ["drawing_property:Revision", "part_property:Revision"],
      "box": { "min": [302.0, 40.0], "max": [330.0, 48.0] },
      "height": 3.5
    },
    "material": {
      "source": ["part_material", "part_property:Material"],
      "box": { "min": [232.0, 30.0], "max": [300.0, 38.0] },
      "height": 3.5
    },
    "finish": {
      "source": ["drawing_intent:finish.general", "part_property:Finish"],
      "box": { "min": [302.0, 30.0], "max": [360.0, 38.0] },
      "height": 3.5
    },
    "general_tolerance": {
      "source": ["drawing_intent:tolerances.general", "drawing_property:GeneralTolerance"],
      "box": { "min": [232.0, 20.0], "max": [300.0, 28.0] },
      "height": 3.5
    },
    "scale": {
      "source": ["sheet:scale"],
      "box": { "min": [302.0, 20.0], "max": [330.0, 28.0] },
      "height": 3.5
    },
    "projection_symbol": {
      "source": ["sheet:projection"],
      "box": { "min": [332.0, 20.0], "max": [360.0, 28.0] },
      "height": 3.5
    },
    "units": {
      "source": ["sheet:units"],
      "box": { "min": [362.0, 20.0], "max": [410.0, 28.0] },
      "height": 3.5
    }
  },
  "revision_table": {
    "box": {
      "min": [230.0, 62.0],
      "max": [410.0, 100.0]
    }
  }
}
```

## Validation Rules

Validation follows the two-stage pipeline of 3.4.7: Draft 2020-12 schema check first, followed by deterministic semantic rules. Semantic rule violations report `IR_RULE_VIOLATED` with a pointer to the invalid element. Numeric comparisons use the length quantum (3.4.3), allowing touching edges.

1. **Paper:** Paper size and orientation must match ISO 5457 (11.2): A4 portrait; A3, A2, A1, A0 landscape.
2. **Border:** Margins must be positive and leave a border rectangle with positive width and height on that paper. If this rule fails, border containment checks are skipped for that document to prevent cascading errors.
3. **Rectangles:** For every rectangle, `min[0] < max[0]` and `min[1] < max[1]`. An inverted rectangle is reported once and then excluded from spatial containment and overlap checks.
4. **Zones:** At least one title block zone must be defined. Every zone must lie within the border rectangle, and no two zones may overlap (touching edges pass).
5. **Lines:** Lines must have non-zero length and must lie entirely within one title block zone.
6. **Boxes:** Every text box must lie within the border rectangle. Every field box and the revision table box must lie entirely within one title block zone (a box straddling two zones is rejected). No two boxes (text, field, or revision table) may overlap.
7. **Text height:** Text height must be positive and no greater than its enclosing box height.
8. **Minimum fields:** The eight minimum fields required by check D8 (`part_number`, `revision`, `material`, `finish`, `general_tolerance`, `scale`, `projection_symbol`, `units`) must all exist in `fields`, and none may set `required: false`. (If omitted, `required` defaults to `true`).
9. **Source order:** Candidates within a field's `source` list must follow non-decreasing ownership rank (`design_intent:` 0, `drawing_intent:` 1, others 2). `sheet:` sources must be the sole candidate in their field.

## Relation to Other Modules

- **Drawing Layout IR (11.11):** A drawing sheet references either `template` (`DocumentRef`, pointing to a `drawing_template` document) or `sheet_format` (path to a hand-made `.slddrt` file), mutually exclusively. When `template` is used, the sheet does not define redundant `size` or `orientation`.
- **Title Block Mapping (13.3.4):** Configuration-based TOML mappings apply only to hand-made `.slddrt` files. Generated formats derived from Drawing Template IR embed their own field sources and geometry, needing no separate TOML file.
- **Drawing Check D8 (11.5.3):** For drawings using generated templates, D8's required fields and revision table expectation are derived directly from the template IR.
- **Bundle Manifest (3.4.5):** Multiple `drawing_template` documents may be present in a single IR bundle, allowing drawings with different sheet formats across sheets.
