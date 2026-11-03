# ADR-033: Project store of plain files

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Project store of plain files; parts identified by PDM ID or path plus fingerprint, never by writing into them; lost state makes annotations pinned, not movable

## Rationale

Keeps ADR-022; survives moved files; never loses an engineer's edits

## Where it applies

- [architecture/data-management.md](../architecture/data-management.md) — section 13.1
