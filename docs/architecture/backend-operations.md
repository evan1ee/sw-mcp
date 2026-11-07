# 6.5 Backend Operations and Execution Plans, 6.6 Capability Profile

> Specification v1.41, sections 6.5–6.6. Index and section map: [specifications/README.md](../specifications/README.md).

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
| Document | `document.open` (path, read-only, fully resolved, configuration), `document.activate`, `document.save` (drawings and exports, and a part the job itself created, ADR-046), `document.close`, `document.rebuild` | 1a (open, close), 1b (rest) |
| Read-back | Not operations: the `drawing.snapshot` and `features.read` commands (ADR-036) and `geometry.candidates` (ADR-049) | 1a, 1b |
| Drawing structure | `drawing.create` (template, sheet format, size), `sheet.add`, `sheet.update`, `view.create` (type, parent, orientation, configuration, scale, position, modifiers, 11.11), `view.update`, `view.delete` | 1b |
| Dimensions | `model_items.insert` (view, source `model` or `dimxpert`, eliminate duplicates), `dimension.hide`, `dimension.show`, `dimension.add_reference` (view, measured entities, kind, text position), `dimension.set_tolerance`, `dimension.set_parentheses`, `dimension.move` (text position, side, offset) | 1b |
| Annotations | `annotation.tag` (pipeline tag, 11.11), `annotation.move`, `note.add`, `hole_callout.add`, `center_mark.add`, `centerline.add`, `gdt.add`, `datum.add`, `surface_finish.add`, `balloon.add`, `table.add` | 1b |
| Drawing data | `drawing_property.set` (title-block values written to the drawing, 11.1), `drawing.link_store` (the drawing ID property, 13.1) | 1b |
| Export | `export.pdf`, `export.dxf` (to a temporary path; the core renames, ADR-046) | 1b |
| Sheet format | `sheet_format.generate` (template `DrawingTemplate`, destination path) | 1b (ADR-055, K7 closed) |
| Part model | `part.create` (template, working file), `sketch.create` (plane, entities, relations, dimensions, 5.7), `feature.create` (type, lowered parameters, pinned references), `feature.update`, `feature.suppress`, `feature.delete`, `body.delete`, `material.set` | 1c (create subset, ADR-029; the MVP subset below), 2 (rest) |
| Part data | `custom_property.set`, `marked_for_drawing.set` — only with the explicit permission of ADR-022 | 1b, behind the permission option |
| Undo | `undo.begin`, `undo.end`, `undo.rollback` (8.5) | P2 (8.5). Part jobs use the working-file rule instead (8.4.1, ADR-046) |

**Part chain MVP subset [Builder's call].** The first part operations, specified by the [MVP design](../superpowers/specs/2026-11-05-part-chain-mvp-design.md) section 7. Their schemas are `schemas/ipc/ops/part.create.json`, `sketch.create.json` and `feature.create.json`.

| Operation | `params` | `result` |
| --- | --- | --- |
| `part.create` | `template`: the full path of a `.prtdot` (see below). The batch's `document` is the working file path, which must not exist | `native_id`, `path`, `instance_id`, `previous_active`, `template` (`path`, `sha256`) |
| `sketch.create` | `node_id`, `plane` (`plane:front`, `plane:top` or `plane:right`), `entities` (`line`: `start`, `end`; `circle`: `center`, `diameter`; lengths in millimetres, 2D sketch coordinates, 5.7.4) | `native_id`, `feature_id`, `entity_count` |
| `feature.create` | `node_id`, `type` (`extrude` or `cut_extrude`), `profile` (the `feature_id` of the sketch), `end_condition` (`blind` with `depth`, or `through_all_both` for a cut) | `native_id`, `feature_id`, `status` |

- **Standard planes are role references.** `plane:front`, `plane:top` and `plane:right` name roles, not pinned persistent IDs. This is a stated exception to 6.5.1's rule that geometry is given only as pinned IDs. The add-in maps each role to the native plane by order and checks its normal (5.7.4).
- **Profile.** `feature.create`'s `profile` is the sketch's `feature_id`, `f<IFeature.GetID()>` (5.3.6). The job binds it (6.5.3).
- **The document is addressed by its full path only.** `GetOpenDocumentByName` finds a document by full path and returns null for a title or an unsaved document.
- **Template.** `part.create` never uses SOLIDWORKS's own default-template preference, which can name a file that does not exist (`~BLANK_PART_TEMPLATE.prtdot`). The caller gives `template`; the core fills it from the configuration key `part.template` (13.3) when the caller names none, and fails with a catalogued error naming that setting when neither exists (8.4). The add-in fails with `FILE_NOT_FOUND` and `details.setting: part.template` when the file is missing. There is no fallback to an installed template. The template is only read.
- **Existing files.** `part.create` and `document.save` refuse a path where a file already exists, with `AUTH_SOURCE_WRITE_NOT_ALLOWED`. `SaveAs4` with the silent option overwrites without warning, so the add-in must not rely on it to refuse.
- **Failure.** A feature call that returns null fails with `BACKEND_REBUILD_ERROR`. The add-in's translator sets `Dir=true` for a blind cut (5.7.4). Neither the plan nor the wire carries a direction (8.9.3 rule 4, ADR-064).
- **Ownership.** The add-in records the working part as owned by the requesting job, and refuses `document.save` and `document.close` on a `.SLDPRT` the requesting job does not own (ADR-046).

## 6.5.3 Execution Plan

The compiler's output for a bundle (6.2). Stored under `derived/plans/` (13.2) and keyed by its content hash.

| Field | Description |
| --- | --- |
| `plan_schema_version` | (ADR-042) |
| `bundle` | The validated bundle with every reference pinned (3.4.5) |
| `provenance` | Compiler version, capability-profile hash (6.6), part fingerprints, recorded geometry candidates (ADR-049) |
| `defaults` | Every default the compiler filled, by node and parameter (5.7) |
| `operations` | Keyed by plan-local ID (ADR-048). Each has `sequence` (integer, the execution order), `document`, `op`, `params`, `source` (the IR item it implements), `depends_on` (plan-local IDs) and `postconditions` |
| `verification_points` | Plan-local IDs where the optional T2 checks may run (10.2.2). Every operation is judged, whether or not it is listed here |

- **Postconditions** name the checks that apply to an operation: `feature_exists`, `feature_status_ok`, `rebuild_ok`, `entity_count`, `parameter_equals` (within the 3.4.3 quantum). The plan holds names only, never expected values. Those come from the contract that `cad-verification` derives from the graph, and the core judges them from the operation's observation (10.2.2, ADR-064). A failed required check ends the job.
- **Batches.** The core sends the operations in `sequence` order, cutting a batch at every verification point and after at most 100 operations. Each batch is journalled before it is sent (13.2.3). A `plan` job sends each operation as its own batch **[Builder's call]**, so an earlier result is always available to bind a later operation.
- **Symbols [Builder's call].** A plan must be byte-identical for the same input, but a working file path and SOLIDWORKS feature IDs exist only at run time. So a plan holds symbols and the job binds them when it sends an operation: an operation's `document` of `$working` becomes the working file path, and a `profile` that is a sketch's node ID becomes the `feature_id` returned for that node. The job keeps the node ID to `feature_id` map in its `part_result` (12.4.5). `template` is absent from the plan and filled in by the job (6.5.2).
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
