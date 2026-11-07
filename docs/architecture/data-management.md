# 13. Data Management and Persistence

> Specification v1.39, section 13. Index and section map: [specifications/README.md](../specifications/README.md).

The system persists enough to reproduce, inspect and recover sessions.

**Entities:** Project, Document, IRBundle, PartFeatureGraph, FeatureNode, AssemblyGraph, DesignIntent, DrawingIntent, ResolvedScheme, DrawingLayout (planned and as-built snapshots), DrawingGeometrySnapshot, GeometryReference, ExecutionPlan, Job (Execution), Operation, VerificationReport, DrawingReport, BackendSession.

**Versioned:** IR schemas, design intents, feature graphs, drawing intents, drawing layouts, compiler, backend, execution plans, verification and drawing reports.

**Traceability:** each execution links to Design Intent revision, Drawing Intent revision, Drawing Layout revision, graph revision, compiler version, backend version, SOLIDWORKS version, plan, operation results and reports.

## 13.1 Storage and Document Identity [Builder's call] (ADR-033)

File layout, write rules, the job journal and retention are in 13.2; configuration is 13.3.

**Where data lives.**
- Each project has a project store: a directory (default `.cad/` at the project root) of JSON files plus a small index. IR modules, Resolved Schemes, layout snapshots, Drawing Geometry Snapshots, reports and the execution journal live there. It is plain files so it can be diffed, backed up and put in version control.
- The drawing file links to its store entry through a drawing custom property holding the drawing ID. Writing it is allowed because the drawing is the pipeline's own output (ADR-022). The part is never written for this purpose.
- `check_drawing` on a drawing the system did not produce writes nothing to the drawing; it identifies the drawing by path and fingerprint only. In the store it creates or updates that drawing's record (13.2.1), so its latest report is kept (13.2.4).

**Document identity.** Source parts cannot carry an ID without being modified (ADR-022), so:
- A part's identity is its PDM document ID when it is vaulted, otherwise its path plus a content fingerprint (SHA-256 of the saved file). A file that moved is matched by fingerprint; if more than one stored document matches, the system asks.
- A part's revision for the read-only Part Feature Graph is its fingerprint. A part with unsaved changes is read as "dirty": allowed for inspection, not for producing a drawing that a later run must reproduce.

**Lost or stale state.** If a drawing's store entry is missing (the SLDDRW was copied elsewhere) or its last as-built snapshot is gone, pins cannot be detected (11.11). The pipeline then treats every existing annotation as pinned, never as movable, and reports that it did so. Engineer edits are never lost because state was lost.

**Concurrent updates.** Every `update_*` and `apply_*` tool takes the `expected_revision` of the module it changes, apart from the `apply_part_graph` exception in 3.4.5. A mismatch is rejected with the current revision; nothing is merged silently.
