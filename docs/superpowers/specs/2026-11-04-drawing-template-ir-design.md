# Drawing Template IR: design

Status: draft for owner approval. Date: 2026-11-04.

## Intent

Today a drawing's sheet format can only be a binary `.slddrt` file supplied by hand. The core never parses those files (13.3.4), so it cannot know where the border or the title-block fields are until SOLIDWORKS reports them, and register item K3 stays blocked.

The owner wants the format itself to be data: a Drawing Template IR that defines paper size, border, title block, static text and attribute links, and from which the system later **generates** the sheet format. This follows the IR-first principle (1.3): the IR is the source, and SOLIDWORKS output is built from it.

## Goals

1. Add `drawing_template` as a new IR module, specified as new section 11.12.
2. Add its JSON Schema, fixtures and a pure validator, so a template can be authored and fully checked without SOLIDWORKS.
3. Update every related document so the spec is consistent, including the planned generation path.

## Non-goals (this round)

- Generating a `.slddrt` or drawing anything in SOLIDWORKS. The add-in and adapters do not exist, so this could not be tested. The backend operation is named in 6.5.2 but has no schema or code.
- MCP tools, project-store records, or the pipeline consuming templates.
- Implementing Drawing Layout IR changes in code: that module is still a scaffold, so only its spec changes.
- Describing or replacing the owner's existing `.slddrt` files. They are not opened or changed (ADR-022), and they stay supported through the 13.3.4 mapping.

## Anti-goals

- Two owners for one value (3.3 rule 4). A generated template owns its fields; there is no TOML mapping beside it.
- Any SOLIDWORKS term or I/O in the module (G2, ADR-054).
- A validator that passes a template which D8 would always fail on.

## Decided by the owner

- The IR **generates** formats; it does not describe existing ones.
- This round stops at spec, schema and validation.

## The module [my calls, for owner review]

**One document is one sheet format:** one paper size and one orientation. A drawing whose continuation sheets use another format uses a second document.

| Field | Contents |
| --- | --- |
| Header | `module: "drawing_template"`, `id`, `schema_version: "0.1"`, `units: "mm"` (always), optional `revision`, optional `display_name` |
| `paper` | `size` (`A4`, `A3`, `A2`, `A1`, `A0`), `orientation` (`portrait`, `landscape`) |
| `border` | `margins` (`left`, `right`, `top`, `bottom`, in mm), optional `line_width` |
| `title_block` | `zones`: rectangles, keyed by item ID, that together make the block (D7 keeps views out of them). `lines`: keyed, each `from`, `to`, optional `line_width` |
| `texts` | Static text, keyed: `text`, `box`, `height`, optional `align` (`left`, `center`, `right`) |
| `fields` | Attribute links, keyed by field name (same names as 13.3.4 and D8): `source`, optional `required`, `box`, `height`, optional `align`, optional `label` |
| `revision_table` | Optional: `box`. Its presence means sheets of this format carry a revision table, as `revision_table = true` does in 13.3.4 |

Coordinates are sheet millimetres from the lower-left corner, as in 11.11. Rectangles use `{min, max}` as in the snapshot (11.5.1), so a template's zones map directly onto what D7 reads.

**Field sources** extend the candidates of 13.3.4: an ordered list where the first one present wins. The schema restricts each entry to:

- `part_property:<name>`, `drawing_property:<name>`, `part_material`
- `design_intent:<path>`, `drawing_intent:<path>`
- `sheet:scale`, `sheet:projection`, `sheet:units` (new: these values belong to the sheet, not the part)

Example (excerpt):

```json
{
  "module": "drawing_template",
  "id": "ACME-A3",
  "schema_version": "0.1",
  "units": "mm",
  "paper": { "size": "A3", "orientation": "landscape" },
  "border": { "margins": { "left": 20, "right": 10, "top": 10, "bottom": 10 } },
  "title_block": {
    "zones": { "main": { "min": [230, 10], "max": [410, 60] } },
    "lines": { "top": { "from": [230, 60], "to": [410, 60] } }
  },
  "texts": {
    "company": { "text": "ACME Ltd", "box": { "min": [232, 50], "max": [300, 58] }, "height": 5 }
  },
  "fields": {
    "part_number": {
      "label": "Part no.",
      "source": ["design_intent:metadata.part_number", "part_property:PartNo"],
      "box": { "min": [232, 40], "max": [300, 48] }, "height": 3.5
    }
  }
}
```

## Validation rules

Schema first, then semantics (3.4.7). Semantic failures use the existing `IR_RULE_VIOLATED` with a pointer to the item; no new error codes. All are errors, reported together in deterministic order. Geometry is compared using the length quantum (3.4.3), so touching edges are allowed.

1. **Paper:** size and orientation follow 11.2: A4 portrait, A3 to A0 landscape.
2. **Border:** margins are positive and leave a border rectangle with positive area on that paper.
3. **Rectangles:** every `min` is below `max` on both axes.
4. **Zones:** at least one, each inside the border, none overlapping.
5. **Lines:** non-zero length, each inside one zone.
6. **Boxes:** each text box is inside the border, each field box and the revision-table box inside one zone. No two of these boxes overlap.
7. **Text height:** positive and no greater than its box height. Text width is not checked: the pure core has no font metrics.
8. **Minimum fields:** the eight D8 minimum fields (`part_number`, `revision`, `material`, `finish`, `general_tolerance`, `scale`, `projection_symbol`, `units`) all exist and none sets `required: false`. They are required even when the flag is omitted.
9. **Source order:** within one field's `source`, candidates follow the ownership order of 3.3 rule 4: `design_intent:`, then `drawing_intent:`, then the part and drawing sources. This stops an author making the wrong owner win. `sheet:` sources stand alone.

`projection_symbol` is an ordinary field in this version: its box reserves the place for the symbol, and how it is drawn is decided with generation.

## How it fits the rest of the system

- **Module key:** `drawing_template` is added to `ModuleKey`, `DocumentRef` and `ItemRef` (`schemas/common/v0.json`, 3.4.1) and to `cad_ir.core.ids`.
- **Composition (3.3):** requires nothing and has no references that bundle validation resolves. It is not a derived artifact: it is authored and revisioned. It is optional, and a Drawing Layout may depend on it.
- **Field sources are late-bound.** `source` entries are not cross-module references. They name where a value is looked up when the title block is filled, and an absent candidate is skipped, as in 13.3.4. 3.3 rule 3 and 3.4.2 rule 3 gain this one stated exception, and bundle validation never resolves them.
- **Bundles (3.4.5):** like `part`, several `drawing_template` documents may be in one bundle, one per format used. `parse_bundle_manifest` changes to allow this, with tests. The same document twice stays an error.
- **Drawing Layout IR (11.11):** a sheet names exactly one of `template` (a `DocumentRef`, for a generated format) or `sheet_format` (a hand-made format). The template is the only owner of what it defines: a sheet naming a `template` has no `size` or `orientation`, the drawing has no `title_block` element for it, and no `tables` entry places its revision table. What was actually produced is still read back through the snapshot (11.5.1), which already carries the sheet size. Hand-made formats keep today's fields.
- **13.3.4:** stays as the mapping for hand-made formats, and says that a generated format has no TOML file.
- **D8 (11.5.3):** the spec gains the rule that, for a generated format, D8's mapping is derived from the template: `fields` with their required flags, and `revision_table`. This round is spec only, because no generated sheet can exist yet, so `cad_drawing.checks` does not change. How a read-back `sheet_format` identifies its template document and revision is decided with generation and listed in K7. Until then, a generated sheet would be `not_evaluated` with `title_block_mapping_missing`, which K7 states.
- **Generated output:** a generated `.slddrt` is a derived artifact (3.3 rule 8), written as a new file and never over an owner's file (ADR-022).
- **K3:** stays open for hand-made formats, with a note that generated formats avoid it by construction once generation exists.

## Layout of the work

**Spec** (v1.24):
- New `docs/architecture/drawing-template-ir.md` (§11.12).
- New ADR-055: IR-generated sheet formats alongside owner-supplied ones. It extends ADR-050, which said the owner supplies the format, and does not withdraw it.
- Register: new item K7, covering the generation path: the SOLIDWORKS calls to create a sheet format, how fields become linked notes, read-back locators, how a generated sheet names its template revision for D8, drawing the projection symbol, and where templates reusable across projects are stored. Blocks `later`.
- Edits for consistency: `overview.md` (3.1–3.3), `shared-ir-core.md`, `drawing-layout-ir.md`, `production-drawings.md` (11.2 title-block row, 11.5.3 D8), `configuration.md`, `backend-operations.md` (a generation operation in 6.5.2, marked later), `roadmap.md`, `repository-structure.md`, `docs/README.md`, `specifications/README.md`, `adr/README.md`, `CHANGELOG.md`, version headers, and any other file that lists the modules.

**Contracts:** `schemas/drawing-template/v0.json`; valid and invalid fixtures in `tests/fixtures/schemas/drawing-template/`; regenerate `cad_ir/generated/`.

**Code:** `cad_ir/drawing_template/`, pure and following `cad_ir.bundle.manifest`: `parse_drawing_template(doc) -> DrawingTemplate | IssueReport` returning frozen dataclasses. Paper dimensions are an ISO 5457 table in this package. Test first, per AGENTS.md.

**Verification:** the full Python suite in AGENTS.md section 4, and the C# tests because `common/v0.json` changes. `HANDOFF.md` is updated at the end.

## Left to the builder

File split within `cad_ir/drawing_template/`, fixture names, exact schema layout, wording, and the order of the work.

## Constraint on the working tree

The branch `feat/check-drawing-job` has uncommitted milestone 5 work that touches some of the same files (`CHANGELOG.md`, `open-decisions.md`, `tests/contract/test_schema_fixtures.py`, generated files). This work sits on top of it, and nothing is committed unless the owner asks.
