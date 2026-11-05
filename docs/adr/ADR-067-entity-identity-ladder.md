# ADR-067: Which native identifiers may name faces, edges and vertices

- **Status:** Proposed
- **Source:** specification v1.35, section 8.9.12; extends ADR-005, ADR-033 and ADR-049. API facts from the installed 2025 help, not measured

## Context

Section 7 names `GetPersistReference3` as the native signal, without saying what else is acceptable. SOLIDWORKS offers several identifiers with different lifetimes. The help states that face IDs are removed whenever a document is rebuilt, tracking IDs live until a rebuild, safe entities do not persist across sessions, and entity names are written into the part. None of this has been measured for entities here.

## Decision

- **Identity is the authored role plus a signature.** A pinned persistent reference is an accelerator, always re-checked by signature on use.
- **Pin with `GetPersistReference3`** and dereference with `GetObjectByPersistReference3`. Never compare the reference's bytes.
- **`GetSafeEntity`** only within one command.
- **Never** face IDs, tracking IDs, macro features or enumeration indexes.
- **Entity names and attributes are not used on parts.** They write to the document, so never on a source part (ADR-022). A job-owned working part is a possible later exception, decided from K28's measurements.
- The add-in never re-resolves. A failed reference fails the operation.

## Rationale

Keeping identity in authored meaning means a reference can be resolved again after any change, and means the file holds nothing of ours, which ADR-033 and ADR-022 require. Each native identifier listed as "never" fails in a documented way for this use.

## Consequences

- A rebuild that changes topology may fail a reference that a written entity name would have followed. That is the conservative failure section 7 asks for.
- K28 may reopen the entity-name exception with evidence.

## Where it applies

- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — section 8.9.12
- [specifications/ir-specification.md](../specifications/ir-specification.md) — section 22.6
- [architecture/geometry-references.md](../architecture/geometry-references.md) — section 7.5
