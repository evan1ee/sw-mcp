# ADR-046: Document ownership, saving and outputs

- **Status:** Proposed
- **Source:** specification v1.13, open decision E2

## Context

The agent works in the engineer's SOLIDWORKS session (8.3 rule 13). The spec says a failed drawing "may be saved for inspection" (11.6) and that undo objects give a cheap rollback (8.5), but not:

- which documents a job may close;
- when it saves;
- whether a re-run may overwrite an existing drawing or PDF;
- where failed output goes.

Each gap can lose an engineer's work or leave their session in a surprising state.

## Decision

**Ownership.**
- A job **owns** the documents it opened. Documents that were already open when the job started are **borrowed**.
- A job closes only documents it owns, at the end of the job. It never closes a borrowed document. Borrowed documents are restored to the active-document state they had.
- A job never saves a borrowed document that had unsaved changes before the job started. If it needs to write such a document, it fails with `EXEC_DOCUMENT_DIRTY` and names it.

**Saving.**
- `check_drawing` never saves anything (8.4).
- `produce_drawing`, `relayout_drawing` and `update_drawing_layout` save the drawing only when the job reaches COMMITTED.
- A job that ends FAILED saves its drawing, if it has one, as `<name>.failed.SLDDRW` beside the target, and the report links it. The target file is never touched by a failed job.
- A cancelled job (ABORTED) saves nothing unless `keep_partial` was set. With `keep_partial`, the result goes to `<name>.partial.SLDDRW`.
- Source parts and assemblies are never saved (ADR-022). That includes no re-save in a newer version and no save of model changes the drawing pipeline caused.

**Overwriting.**
- An existing `.SLDDRW` is overwritten only when its drawing ID property links it to a record in this project's store (13.1), proving the system produced it. Otherwise the job fails with `AUTH_SOURCE_WRITE_NOT_ALLOWED`, and the agent must choose a new path.
- Before overwriting, the previous file is copied to `.cad/backups/<drawing_id>/<timestamp>.SLDDRW`. The last 5 copies are kept (`store.backup_keep`, 13.3).
- Exports (PDF, DXF) are written under a temporary name and renamed into place only when complete, so a reader never sees a half-written file. An existing export is replaced only under the same rule as its drawing.

**Rollback.**
- Part plans (Phase 1c on) are wrapped in an undo object (8.5) and rolled back on failure unless `keep_partial` is set.
- Drawings are not rolled back through undo, since the target file is never written by a failed job. The `.failed` copy is the evidence.

## Rationale

Splitting owned from borrowed documents gives the engineer one simple promise: the agent cleans up after itself and never closes or saves what they had open. Writing failed and partial results beside the target, never over it, keeps inspection possible without ever damaging a good drawing. The ownership proof through the store link reuses ADR-033 and needs no new metadata.

## Consequences

- The add-in tracks, per job, which documents it opened and the session's active document at the start.
- `.failed` and `.partial` files accumulate beside targets. Reports name them, and the engineer deletes them.
- Adds `EXEC_DOCUMENT_DIRTY` to the error catalogue (ADR-037).

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.3 rule 13, 8.4, 8.5, 8.6
- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.4, 11.6
- [architecture/data-management.md](../architecture/data-management.md) — section 13.1, 13.2
- [api/tool-contracts.md](../api/tool-contracts.md) — section 12.5
- [ADR-022](ADR-022-never-modify-source-parts-without-permission.md), [ADR-033](ADR-033-plain-file-project-store.md)
