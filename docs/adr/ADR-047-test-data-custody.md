# ADR-047: Test data, benchmark files and holdout custody

- **Status:** Proposed
- **Source:** specification v1.13, open decision T2

## Context

The drawing benchmark (11.8) and the CAD benchmark (15.4) consist of SOLIDWORKS binaries: large, tied to the SOLIDWORKS version that saved them, and changed rarely. The holdout set consists of the owner's real, possibly confidential parts, and the builder must not see them during development (11.8). Recorded IPC transcripts and Drawing Geometry Snapshots (11.5.1, 15.5) are generated from these files. Nothing says where any of it lives or who may read it.

## Decision

| Data | Lives in | Who can read it | Format rules |
| --- | --- | --- | --- |
| Builder-made benchmark parts, reference drawings, their IR files | This repository, under `tests/drawing-benchmark/` and `tests/cad-benchmark/`; binaries in Git LFS | Everyone with repository access | Saved in the oldest supported SOLIDWORKS version (ADR-045). Each part has a `README` with its purpose, features and profile |
| Owner-approved reference drawings | Same, plus the approval record (`approved_by`, date, revision) | Everyone with repository access | A reference drawing changes only with a new approval |
| Recorded snapshots and IPC transcripts of benchmark parts | `tests/fixtures/` (JSON, not LFS) | Everyone | Re-recorded by the live suite; the diff is reviewed like code (15.5) |
| Holdout parts and their IR files | Only on the SOLIDWORKS CI machine, in a folder the builder's accounts cannot read, owned by the owner | The holdout workflow's runner account and the owner | Never committed; never copied off the machine |
| Holdout results | Published by the holdout workflow | Everyone | Aggregate pass/fail per check and a failure analysis per part. No snapshots, part names or geometry unless the owner releases them |

- The holdout workflow (ADR-039) runs only on manual dispatch at increment acceptance. It writes its raw snapshots and logs to the protected folder only.
- A failure analysis that needs the builder to see a holdout part needs the owner's release of that part. A released part moves into the regular benchmark and stops being holdout. The owner replaces it to keep the holdout set at 5–10 parts.
- Real customer data never enters unit-test fixtures. Fixtures from owner parts outside the holdout set need the owner's approval, recorded in the fixture's metadata.

## Rationale

Git LFS keeps large binaries out of the regular history while still versioning them with the code that uses them. Holding the holdout set on the one machine that needs it, under the owner's control, is the simplest arrangement that keeps it unseen, which is what makes its results meaningful.

## Consequences

- Contributors need Git LFS installed. CI jobs that do not need SOLIDWORKS skip the LFS download.
- Upgrading the oldest supported SOLIDWORKS version (ADR-045) means re-saving all benchmark binaries in one reviewed change.
- The owner has a recurring task: approve references and maintain the holdout folder.

## Where it applies

- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.8
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.4, 15.5
- [ADR-039](ADR-039-monorepo-and-ci.md), [ADR-045](ADR-045-solidworks-version-compatibility.md)
