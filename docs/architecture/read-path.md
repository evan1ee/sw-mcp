# 5.8 Read Path: Feature Tree to Read-only Part Feature Graph

> Specification v1.43, section 5.8. Index and section map: [specifications/README.md](../specifications/README.md).

Phase 1b drawings mostly document hand-modelled parts (ADR-029). The Read path turns such a part's feature tree into a read-only Part Feature Graph (`origin: read`, 5.1), so Drawing Intent, the Resolved Scheme and check D4 can refer to its features and parameters by stable IDs.

## 5.8.1 When it runs

- `get_feature_tree` (12.4.4) reads a part through the add-in's `features.read` command (ADR-036), page by page, stores the result, and returns its `DocumentRef` with a summary page.
- `produce_drawing` and `check_drawing` with a Drawing Intent run it when the part has no read graph for its current fingerprint.
- Reading never changes the part (ADR-022).

## 5.8.2 Documents

- **One document per part and configuration**, because dimension values and suppression differ per configuration. The document ID is `<part_key>--<configuration slug>`:
  - `<part_key>` is from 13.2.1 (`pdm-4711`, `fp-3c9e01a7b2d45f60`);
  - the slug is the configuration name in lower case with every run of other characters replaced by `-`;
  - if the name had non-ASCII characters, `-<hash6>` of the original name is appended, so localized names stay distinct.

  For example: `part:pdm-4711--default`.
- **Revisions** follow the part's fingerprint (3.4.5): reading an unchanged part returns the existing revision; a changed part gets a new one. Node IDs stay the same across revisions as long as SOLIDWORKS keeps the features' IDs (A2).
- **Unsaved changes.** A part with unsaved changes is read for inspection only: the result is returned with `dirty: true` and is not stored as a revision. `produce_drawing` refuses a dirty part (13.1).

## 5.8.3 Nodes and parameters

| Item | Rule |
| --- | --- |
| Node ID | `f<IFeature.GetID()>`, for example `f12`. If assumption A2 fails for a case, `p<first 8 hex of the hash of the persistent reference>` (5.3.6) |
| `type` | The registry type when recognized (5.7), else `unrecognized` |
| `native_type` | `IFeature.GetTypeName2`, always kept |
| `display_name`, `tree_order` | The localized name and position in the tree, for reports only (5.3.6) |
| Dimensions | Every display dimension of the feature (generic dimension read, 5.3.1), keyed `d<index>` in the feature's own enumeration order: `f12.d1`. Each has `value`, `kind` (`linear`, `angular`, `diameter`, `radius`), `full_name` (for reporting and `swdim:` matching), and `driven_by` when an equation, global variable or link drives it (5.3.2, D4) |
| Attributes | For recognized types, the drawing-relevant data the type's Read schema defines: hole standard, size and thread; bend angle, radius and direction; draft angle; pattern count and spacing; with `dimension` links to the `d<index>` that holds each value when one does |
| Sketches | Sketch nodes carry their dimensions and `fully_defined`. Sketch geometry is not read in Phase 1 |
| Equations | A document-level `equations` collection, keyed by `e<index>`: the expression text, the dimensions it drives, and the global variables it uses |
| Configuration data | Suppression state and configuration-specific values for this document's configuration |

- Assumption A2's live test also checks that a feature's dimension enumeration order is stable across save/reopen, rename and rebuild. If it is not, parameter keys fall back to the dimension's own name (`D1`), which survives feature renames but not dimension renames, and the report says so.
- **Unrecognized features** keep their dimensions, so D4 still works on them. Every report lists them by type and display name; they are never ignored silently (5.3.1).
- **Roles** (5.7.5) work on read nodes of recognized types exactly as on built nodes, through `geometry.candidates` (ADR-049).

## 5.8.4 Converting `swdim:` references

At Drawing Intent intake (ADR-049), each `swdim:<name>@<feature>[@<file>]` reference:
1. finds the feature whose current display name matches `<feature>` in the part being documented;
2. finds the dimension in that feature whose `full_name` matches;
3. is replaced by the `ParamRef` `f<id>.d<index>`, with the full name kept for reporting.

A name that matches no feature, or more than one, fails intake with `IR_REFERENCE_UNRESOLVED` and lists close matches. A renamed or localized name is never guessed (5.3.6).
