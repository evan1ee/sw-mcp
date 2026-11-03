# ADR-029: Phase 1 is Read-first

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Phase 1 is Read-first: Tier 1 Read for every feature, Create only for what the IR-built benchmark parts need

## Rationale

The drawing pipeline works mainly on hand-modelled parts; keeps Phase 1 within the anti-overengineering goal

## Where it applies

- [architecture/part-feature-graph-ir.md](../architecture/part-feature-graph-ir.md) — section 5.3.2
- [specifications/product-spec.md](../specifications/product-spec.md) — section 2.1
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18
