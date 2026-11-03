# ADR-028: The C# executor runs in process as a SOLIDWORKS add-in, with local IPC to Python

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

The C# executor runs in process as a SOLIDWORKS add-in, with local IPC to Python

## Rationale

Cross-process COM is too slow for drawing read-back; the add-in gets SOLIDWORKS's STA thread and document events

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2
- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18
