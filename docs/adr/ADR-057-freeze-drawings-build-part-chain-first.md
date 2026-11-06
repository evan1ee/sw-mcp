# ADR-057: Freeze drawing work and build the part chain first

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.28, section 18; the owner's request after the [2026-11-05 architecture review](../superpowers/review/2026-11-05-architecture-review.md)
- **Amends:** the order in ADR-029 (Read first) and ADR-030 (1a, then 1b, then 1c). Their other content stands.

## Context

Section 18 builds drawing checks and the drawing pipeline before any part is built from IR. Drawing work has reached a live test script, but the architecture review found it is not yet evidence of correct drawings (F1 to F3). Nothing exists for the part chain: the Part Feature Graph schema, compiler, Execution Plan schema and part operations are all unbuilt.

The owner wants the system to prove the full chain from IR to a real SOLIDWORKS part before more drawing work is done.

## Decision

1. **Freeze the drawing implementation at commit `eea9389`.** It is recorded in the [freeze record](../superpowers/review/2026-11-05-drawing-freeze.md). It is not accepted, and it is not abandoned.
2. **Move development to the Part Feature Graph IR and the part chain.** The goal is an end-to-end MVP: Part Feature Graph IR, compiler, Execution Plan, executor, and a verified `.SLDPRT` as output.

**While frozen:**

- No new drawing features, operations, checks or tools, and no fixes aimed only at drawing code.
- Shared code (add-in host, IPC, job engine, store) may change when the part chain needs it. The drawing tests must keep passing.
- The drawing specification stays in place. It describes the intended design, not finished behaviour.

The owner lifts the freeze by a later decision.

## Rationale

- The part chain is entirely missing, while drawing work already has enough in place to resume from.
- Building a part from IR exercises the core of the design (IR-first, deterministic compilation, verified execution, principle 1.3) in the smallest end-to-end form.
- Freezing, with a record, keeps a clear line between what works and what is unproven. Further drawing work would add features on read-back that does not yet read real geometry.

## Consequences

- **Easier:** one line of development, and early evidence for the compiler, operation and verification contracts.
- **Harder:** hand-modelled parts get no drawing path for now, and the Phase 1a and 1b acceptance dates move out.
- **Risk left in place:** the frozen `check_drawing` can act on the wrong document and close an engineer's open drawing (F4, F5). Use it on scratch copies only.
- **The MVP does not complete Phase 1c.** Phase 1c acceptance also requires benchmark parts and drawings passing D1 to D10.
- **Deferred:** owner decisions O1, O3, O5 and O6, ADR-056, and open decisions K3, J11, K8, K9 and K10 all wait for the freeze to lift. O3 can still be done at any time, since it only corrects a label.
- **To settle in the MVP design, not here:** the first part, what "verified" requires, saving a new part (6.5.2 limits `document.save` to drawings and exports) and failure handling (ADR-046 relies on undo, which A6 has not proven). Changes to those contracts go through the spec first.

## Where it applies

- [specifications/roadmap.md](../specifications/roadmap.md) — section 18
- [drawing freeze record](../superpowers/review/2026-11-05-drawing-freeze.md)
- [ADR-029](ADR-029-phase-1-is-read-first.md), [ADR-030](ADR-030-phase-1-increments.md)
