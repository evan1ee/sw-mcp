# ADR-031: Checks run on a versioned Drawing Geometry Snapshot, separate from the Layout IR

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Checks run on a versioned Drawing Geometry Snapshot, separate from the Layout IR

## Rationale

The Layout IR holds positions, not line and text geometry; one recorded format serves checks, offline tests, benchmark replay and report evidence

## Where it applies

- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.5.1
