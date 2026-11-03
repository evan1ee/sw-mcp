# ADR-030: Phase 1 ships as 1a (checks on existing drawings), 1b (pipeline on hand-modelled…

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Phase 1 ships as 1a (checks on existing drawings), 1b (pipeline on hand-modelled parts), 1c (IR-built parts); the reference implementation runs alongside until parity at the end of Phase 2

## Rationale

Puts the riskiest, most valuable part (read-back and checks) first; removes reference parity from the Phase 1 critical path without losing capabilities

## Where it applies

- [specifications/roadmap.md](../specifications/roadmap.md) — section 18
