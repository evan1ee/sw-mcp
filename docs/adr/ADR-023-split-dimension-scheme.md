# ADR-023: The dimension scheme is split

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

The dimension scheme is split: authored entries (`critical_dimensions`, `scheme_overrides`) live in the Drawing Intent IR; the pipeline-owned Resolved Scheme holds the full derived result; the Layout IR only places it

## Rationale

Checks D4–D6 need one record of what is dimensioned; engineer overrides survive regeneration; regenerating does not bump the intent revision or make agents resend derived data (revised in 1.9)

## Where it applies

- [architecture/drawing-intent-ir.md](../architecture/drawing-intent-ir.md) — section 11.10.1
