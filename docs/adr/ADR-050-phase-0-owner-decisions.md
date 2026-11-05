# ADR-050: Phase 0 owner decisions

- **Status:** Accepted (owner, 2026-11-04)
- **Source:** specification v1.18, roadmap section 18 (Phase 0 owner decisions)

## Context

Section 18 lists decisions only the owner can make: whether the agent shares the engineer's SOLIDWORKS session, the general tolerance designation, how QA balloons are made, whether the pipeline may write into parts, and PDM usage. Until they were made, the spec carried Builder's-call defaults (8.3 rule 13, 11.2, 11.4, ADR-022).

## Decision

| Topic | Decision | Spec impact |
| --- | --- | --- |
| SOLIDWORKS session | The agent shares the engineer's open SOLIDWORKS session under 8.3 rule 13. No dedicated second instance. | 8.3 rule 13; assumption A12 is still proven by its live test, and its fallback stays available |
| General tolerance designation | The title block and the Drawing Intent default carry `ISO 2768-m` together with ISO 22081 (general geometrical specification), not the combined `ISO 2768-mK`. | 11.2, 11.10 `general_tolerance` |
| QA balloons | Note-based balloons attached to dimensions, created by the pipeline. The SOLIDWORKS Inspection add-in is not used. | 11.2 QA overlay |
| Writes into source parts | Allowed for two purposes only: writing custom properties (title-block data) and changing `MarkedForDrawing` flags. Both are off by default and enabled per tool call by an explicit option. Every write is logged with its `request_id` (G3). All other part changes stay forbidden. | ADR-022, 11.1, 11.4 |
| PDM | Not used. Parts are identified by path plus fingerprint (13.1). The PDM rules stay in the spec for other installations. | none |

Still open with the owner: the holdout parts (11.8). The owner will supply the company sheet format; the benchmark parts and reference drawings follow later.

## Rationale

- Sharing the session avoids a second license seat and matches how the engineer works.
- ISO 2768-2 (the `K`) is withdrawn and superseded by ISO 22081, so the current designation avoids citing a withdrawn standard.
- Note-based balloons need no extra add-in or license.
- An opt-in per call keeps ADR-022's default (no side effects on released models) while allowing the A8 fallback and title-block filling when the agent asks for it explicitly.

## Consequences

- The tool contracts that run the drawing pipeline gain an optional input that enables part writes (custom properties, `MarkedForDrawing`). Without it, the pipeline fills gaps only in the drawing.
- The "AI job running" banner and the interruption rules of 8.3 rule 13 are the normal path, not a fallback.
- **Amendment, owner decision D1 (2026-11-05): temporary exception for the part chain MVP.** The banner and its Stop button are not built for the MVP, and `plan` jobs run without them; `cancel_execution` is the way to stop a job. The interruption rules of 8.3 rule 13 (detecting the engineer's edit, save or close of the job's part through document events) are still built. The exception ends when the banner is built, and it does not change the shared-session decision above.
- Shops that read `ISO 2768-mK` can still override `general_tolerance` per part (11.10).

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.3 rule 13
- [architecture/production-drawings.md](../architecture/production-drawings.md) — sections 11.1, 11.2, 11.4
- [architecture/drawing-intent-ir.md](../architecture/drawing-intent-ir.md) — section 11.10
- [ADR-022](ADR-022-never-modify-source-parts-without-permission.md)
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18
