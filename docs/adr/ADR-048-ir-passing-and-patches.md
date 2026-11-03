# ADR-048: Passing IR to tools, ID-keyed collections and JSON Patch updates

- **Status:** Proposed
- **Source:** specification v1.14, open decision M2

## Context

Tools such as `apply_part_graph`, `create_drawing_intent`, `update_drawing_intent` and `produce_drawing` all take IR. The spec did not say:

- whether an agent sends a whole document on every call or a reference to a stored revision;
- what an `update_*` call carries;
- how a change addresses one item inside a document.

That choice drives the token cost (12.3), the revision checks (13.1) and every tool schema (12.4). It also exposed a schema problem: every collection in the examples was an array, and standard JSON Patch (RFC 6902) addresses array items by position. A patch to `/nodes/3` silently hits the wrong node after any insertion.

## Decision

**1. Collections of identified items are JSON objects keyed by item ID**, in every IR module and derived artifact: feature nodes, sketch entities, relations and dimensions, critical dimensions, GD&T entries, surface-finish exceptions, requirements, components, mates, sheets, views, annotations and Resolved Scheme entries. The key is the item ID (3.4.1). The item itself has no `id` field. Order is never carried by key order (JCS sorts keys, 3.4.4). Where order matters, the item has an explicit field (`sequence` for plan operations, `tree_order` for read features). Arrays remain only for ordered values (coordinates, sketch-point lists) and for sets of references (`covers`, `targets`, `dependencies`), which are sorted when hashed (3.4.4).

**2. Creating sends the document by value, once.**
- `create_*` and `apply_*` take the complete module document and return `{ref, revision, content_hash, validation}`, where `ref` is the pinned `DocumentRef` (3.4.2). The document is never echoed back (12.3 rule 5).
- A document that fails validation is not stored. The call returns the errors (3.4.7), and the agent resends.

**3. Changing sends a patch.**
- `update_*` takes `{ref, expected_revision, patch}`. `patch` is an RFC 6902 JSON Patch, applied to the stored revision. Paths use item IDs thanks to rule 1: `/nodes/bore_1/parameters/diameter`, `/critical_dimensions/bore_dia/tolerance`.
- At most 200 operations per patch. A larger rework replaces the whole document with one `replace` at path `""`.
- The patch is applied, the result validated, and a new revision stored only if both succeed; otherwise nothing changes. A `test` operation failing is `REV_CONFLICT`, like a wrong `expected_revision`.
- Patches are stored with the revision they produced, so the history shows what changed.

**4. Everything else takes references.**
- Jobs, compilation, validation and inspection tools take `DocumentRef`s or a bundle manifest (3.4.5), never inline documents. A floating reference is pinned when the call starts and recorded in the job.
- A bundle can only list stored documents. A one-call path stays for simple tasks: `apply_part_graph` stores its graph and builds it (12.4.4).
- Read-only Part Feature Graphs are created by `get_feature_tree` (5.8), which returns their `DocumentRef`.

## Rationale

- Sending a document once and patching it afterwards keeps per-call tokens proportional to the change, not to the document.
- ID-keyed collections make standard JSON Patch safe and its paths readable. Standard libraries in Python and C# can apply patches, so there is no custom patch dialect.
- Taking references everywhere else gives every job a pinned, reproducible input.

## Consequences

- Every example in the specification changes from arrays of `{id, …}` to objects keyed by ID (done in v1.14).
- Schema authors model each identified collection as an object with `propertyNames` constrained to the item ID grammar, so a bad key is a schema error.
- The tool contract version (ADR-042) starts with these input shapes, so no migration is needed.

## Where it applies

- [architecture/shared-ir-core.md](../architecture/shared-ir-core.md) — section 3.4.1, 3.4.5, 3.4.7
- [api/tool-contracts.md](../api/tool-contracts.md) — section 12.4.2, 12.4.4
- [architecture/data-management.md](../architecture/data-management.md) — section 13.1
- [ADR-035](ADR-035-json-schema-contracts.md), [ADR-042](ADR-042-contract-compatibility.md)
