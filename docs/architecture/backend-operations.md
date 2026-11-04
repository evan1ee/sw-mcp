# 6.5 Backend Operations and Execution Plans, 6.6 Capability Profile

> Specification v1.25, sections 6.5–6.6. Index and section map: [specifications/README.md](../specifications/README.md).

The compiler (section 6) and the drawing pipeline (11.4) change SOLIDWORKS only through **backend operations**, sent in `ops.apply` batches over the add-in pipe (ADR-036). This vocabulary is the contract between the Python side and the C# adapters.

## 6.5.1 Operation

```json
{ "op": "dimension.hide",
  "params": { "annotation": "sp:a_bore_x", "reason": "replaced_by:ds_sketch_bore_x_4556c0" } }
```

Every operation type has a schema in `schemas/ipc/ops/<op>.json` (ADR-035) with:

| Field | Description |
| --- | --- |
| `op` | `<object>.<verb>` name, unique. (Operation names are internal, so they are not bound by the MCP naming rule of ADR-040) |
| `params` | JSON Schema. Geometry is given only as pinned persistent reference IDs (ADR-049); lengths and angles in the units of 3.4.3; annotations by their pipeline tag (11.11) |
| `result` | JSON Schema of what the add-in returns: created native IDs and tags, read-back values |
| `mutates` | `document` (changes a document), `session` (opens, closes or activates) or `none` |
| `errors` | Error codes it may return (ADR-037) |
| `since` | Protocol minor version that introduced it (ADR-042), and the named API capability it needs, if any (ADR-045) |

Rules:
- **Idempotency.** Every operation in a batch carries an operation ID (`<job_id>:<seq>`, 13.2.3). The add-in records completed IDs and answers a repeated ID with `DUPLICATE_OPERATION` and the original result (ADR-032).
- **One document per operation.** An operation acts on one document, named in the batch header. A batch may span documents, in order.
- **No interactive helpers.** Creation follows 8.3 rule 11 (`AddToDB`, no inference, selection by entity). Every operation leaves the document in the selection and edit state it found it in.
- **Failure stops the batch.** The first failing operation ends the batch. The response lists completed operation IDs and the failing one with its error. Later operations are not attempted.

## 6.5.2 Vocabulary

Operation groups and the increment that needs them. Each group's schemas are written before that increment starts.

| Group | Operations | Needed by |
| --- | --- | --- |
| Document | `document.open` (path, read-only, fully resolved, configuration), `document.activate`, `document.save` (only drawings and exports, ADR-046), `document.close`, `document.rebuild` | 1a (open, close), 1b (rest) |
| Read-back | Not operations: the `drawing.snapshot` and `features.read` commands (ADR-036) and `geometry.candidates` (ADR-049) | 1a, 1b |
| Drawing structure | `drawing.create` (template, sheet format, size), `sheet.add`, `sheet.update`, `view.create` (type, parent, orientation, configuration, scale, position, modifiers, 11.11), `view.update`, `view.delete` | 1b |
| Dimensions | `model_items.insert` (view, source `model` or `dimxpert`, eliminate duplicates), `dimension.hide`, `dimension.show`, `dimension.add_reference` (view, measured entities, kind, text position), `dimension.set_tolerance`, `dimension.set_parentheses`, `dimension.move` (text position, side, offset) | 1b |
| Annotations | `annotation.tag` (pipeline tag, 11.11), `annotation.move`, `note.add`, `hole_callout.add`, `center_mark.add`, `centerline.add`, `gdt.add`, `datum.add`, `surface_finish.add`, `balloon.add`, `table.add` | 1b |
| Drawing data | `drawing_property.set` (title-block values written to the drawing, 11.1), `drawing.link_store` (the drawing ID property, 13.1) | 1b |
| Export | `export.pdf`, `export.dxf` (to a temporary path; the core renames, ADR-046) | 1b |
| Sheet format | `sheet_format.generate` (template `DrawingTemplate`, destination path) | 1b (ADR-055, K7 closed) |
| Part model | `sketch.create` (plane, entities, relations, dimensions, 5.7), `feature.create` (type, lowered parameters, pinned references), `feature.update`, `feature.suppress`, `feature.delete`, `body.delete`, `material.set` | 1c (create subset, ADR-029), 2 (rest) |
| Part data | `custom_property.set`, `marked_for_drawing.set` — only with the explicit permission of ADR-022 | 1b, behind the permission option |
| Undo | `undo.begin`, `undo.end`, `undo.rollback` (8.5) | 1c |

## 6.5.3 Execution Plan

The compiler's output for a bundle (6.2). Stored under `derived/plans/` (13.2) and keyed by its content hash.

| Field | Description |
| --- | --- |
| `plan_schema_version` | (ADR-042) |
| `bundle` | The validated bundle with every reference pinned (3.4.5) |
| `provenance` | Compiler version, capability-profile hash (6.6), part fingerprints, recorded geometry candidates (ADR-049) |
| `defaults` | Every default the compiler filled, by node and parameter (5.7) |
| `operations` | Keyed by plan-local ID (ADR-048). Each has `sequence` (integer, the execution order), `document`, `op`, `params`, `source` (the IR item it implements), `depends_on` (plan-local IDs) and `postconditions` |
| `verification_points` | Plan-local IDs after which API verification runs (10.2 layer 1) |

- **Postconditions** are checks the add-in or core runs after an operation: `feature_exists`, `feature_status_ok`, `rebuild_ok`, `entity_count`, `parameter_equals` (within the 3.4.3 quantum). A failed postcondition fails the operation.
- **Batches.** The core sends the operations in `sequence` order, cutting a batch at every verification point and after at most 100 operations. Each batch is journalled before it is sent (13.2.3).
- **Operation IDs.** A plan's IDs are plan-local, so one plan can be executed by several jobs. At execution, the job turns each into `<job_id>:<sequence>`.
- **The drawing pipeline does not compile a plan up front.** Each pipeline step (11.4) emits batches of the same operations, journalled the same way, and its report records them.

## 6.6 Backend Capability Profile

What the compiler and the drawing pipeline may assume about the connected backend. The profile is assembled when the core connects to the add-in, and it is recorded, as a content hash, in every plan and report.

| Part | From | Contents |
| --- | --- | --- |
| Backend | Add-in, in `session.hello` (ADR-036) | SOLIDWORKS version and service pack, UI language, add-in and protocol versions |
| Operations | Add-in | Every supported `op` with its schema version |
| API capabilities | Add-in | Named capabilities set from the running version (ADR-045) |
| Licensed modules | Add-in | Whether DimXpert/MBD, SOLIDWORKS Inspection and Motion are available, since some profiles and later phases depend on them (11.3, 5.6) |
| Feature coverage | Core (compiler version) | Per feature type: Create, Read or neither (5.3) |

- **Before execution,** the compiler checks every lowered operation and feature type against the profile. A missing one fails compilation with `COMPILE_UNSUPPORTED_FEATURE` or `BACKEND_CAPABILITY_MISSING`, never at execution time.
- **A changed profile** (SOLIDWORKS restarted on another service pack, a module unlicensed) has a different hash. Cached plans keyed by the old hash are not reused.
- `inspect_cad_file` and the drawing report show the profile in summary form, so an agent can see why something is unavailable.
