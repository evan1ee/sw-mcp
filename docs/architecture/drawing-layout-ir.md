# 11.11 Drawing Layout IR

> Specification v1.18, section 11.11. Index and section map: [specifications/README.md](../specifications/README.md).

## Purpose

The Drawing Layout IR describes how a drawing is arranged: sheets, views, annotation positions, text layout and pinned annotations. It holds no engineering meaning. Every annotation points to a Drawing Intent item (a Resolved Scheme entry, a `gdt` entry, a datum, a surface finish) or is a pure drafting element (center mark, centerline, view label). Moving an annotation in the Layout IR never changes what it says (section 3.3).

## Planned and as-built

Each drawing revision keeps two snapshots in the same schema:

- **Planned:** what view planning and the placement engine decided and the executor applied.
- **As-built:** what was read back from SOLIDWORKS after applying, derived from the Drawing Geometry Snapshot (11.5.1).

Drawing checks run on the Drawing Geometry Snapshot behind the as-built layout, not on the layout itself, which holds positions but not line and text geometry. The diff between planned and as-built shows where SOLIDWORKS placed something differently from the plan. Comparing the as-built snapshot at the start of a later run with the last stored as-built snapshot shows manual edits.

## Structure

| Element | Fields |
| --- | --- |
| drawing | schema_version, units (`mm`, sheet coordinates), drafting standard, template, part path, `intent` (`DocumentRef` pinned to a revision, e.g. `drawing_intent:BRK-001-DI@3`) |
| sheets | Keyed by sheet ID (3.4.1): size (ISO 5457), orientation, sheet format, `scale` (the sheet's default scale; a view may override it) |
| views | Keyed by view ID: sheet, type (`base`, `projected`, `section`, `aligned_section`, `removed_section`, `broken_out_section`, `detail`, `auxiliary`, `flat_pattern`, `isometric`), modifiers (`broken`: break lines and gap, for long parts such as shafts; `crop`: crop profile), parent view, orientation, configuration, scale (ISO 5455), position (view center), display (hidden lines, tangent edges), section line or detail circle with label |
| annotations | Keyed by annotation ID: kind (`dimension`, `callout`, `note`, `gdt`, `datum`, `surface_finish`, `center_mark`, `centerline`, `balloon`), `intent_ref` (an `IntentItemRef`, 3.4.2, or null for pure drafting elements), view, text position, dimension-line side/offset, leader points, text (height, alignment, wrap width), `tag` (pipeline-written identity used to match across runs, see Pins), `native_id` (SOLIDWORKS annotation name, for reporting), `placed_by` (`pipeline` \| `manual` \| `agent`), `pinned` |
| tables | Bend table, hole table, inspection table, revision table: sheet, anchor, position |
| title_block | Field → value source (part property, drawing property, Design Intent or Drawing Intent path). Values themselves are not stored here |

Coordinates are sheet millimetres from the lower-left sheet corner, and angles are in degrees. The adapter converts them to and from SOLIDWORKS metres (8.3).

Example (excerpt):

```json
{
  "module": "drawing_layout",
  "id": "BRK-001-DL",
  "schema_version": "0.1",
  "units": "mm",
  "intent": "drawing_intent:BRK-001-DI@3",
  "sheets": { "s1": { "size": "A3", "orientation": "landscape", "scale": "1:1" } },
  "views": {
    "v_front": { "sheet": "s1", "type": "base", "orientation": "front",
      "configuration": "Default", "scale": "1:1", "position": [140, 170],
      "display": { "hidden_lines": false, "tangent_edges": "removed" } },
    "v_sec_a": { "sheet": "s1", "type": "section", "parent": "v_front",
      "label": "A", "position": [300, 170] }
  },
  "annotations": {
    "a_bore_dia": { "kind": "dimension", "intent_ref": "scheme:ds_bore_1_diameter_b41219",
      "view": "v_sec_a", "text_position": [318.5, 204.0],
      "tag": "sp:a_bore_dia", "native_id": "RD3@Drawing View2",
      "placed_by": "manual", "pinned": true },
    "a_cm_bore": { "kind": "center_mark", "intent_ref": null,
      "view": "v_front", "placed_by": "pipeline", "pinned": false }
  }
}
```

## Pins

- **Automatic.** An annotation becomes pinned (`placed_by: manual`) when a later run detects that someone else changed its position, side, leader or text layout since the last as-built snapshot. The threshold for a position change is 0.5 mm **[Builder's call]**. Annotations also move on their own when the model geometry changes, when a view is moved or rescaled, and when SOLIDWORKS re-snaps text. These are not manual edits. Positions are therefore compared in view coordinates, relative to the annotation's attachment points, and a change counts as manual only when the attachment itself did not move. A model change that moves the attached geometry never pins anything.
- **Identity.** Annotations are matched across runs by a tag the pipeline writes, not by the native name alone. Native names such as `RD3@Drawing View2` contain localized view names and change when a dimension is hidden and re-inserted. Phase 0 proves a durable tag that survives save/reopen: a pipeline-set annotation name, or a SOLIDWORKS attribute. `native_id` is kept for reporting. An annotation that has lost its tag is reported, not guessed **[Builder's call]**.
- **Explicit.** An agent or engineer can pin or unpin through `update_drawing_layout`. Unpinning is always explicit. Re-layout never unpins.
- **Pinned annotations are never moved, hidden or restyled** by `relayout_drawing` or by re-checks after model changes (11.6, 11.7). If a pinned annotation takes part in a hard-check failure, the conflict list reports it.
- **Manual deletion.** If an engineer deletes an annotation whose Resolved Scheme entry is `shown`, the pipeline does not add it back silently. It reports a D4 conflict until the engineer either hides the entry through a scheme override in the Drawing Intent IR or allows it to be re-added.

## Determinism

The same Drawing Intent revision, model state, drafting standard and placement engine version produce the same planned layout. Pinned annotations are inputs to placement: the engine places everything else around them.
