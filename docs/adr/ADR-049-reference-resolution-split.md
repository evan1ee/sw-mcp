# ADR-049: The add-in gathers geometry facts, Python resolves references

- **Status:** Proposed
- **Source:** specification v1.14, open decision C3

## Context

Geometry references (section 7, and the Phase 1 stopgap in 11.1) have to be turned into concrete SOLIDWORKS entities. The compiler pipeline puts the Geometry Resolver in Python (6.2), but resolving needs the live model (7.5), and drawing references must also be mapped into a particular view. Doing it in Python by querying entity by entity breaks the coarse-command rule (ADR-032). Doing it in C# moves confidence scoring, role rules and ambiguity handling into the add-in, where they cannot be tested offline. Phase 1b needs the stopgap forms (`feature.role`, `geo:`, `swdim:`) and Phase 1c the compiler. Choosing late would mean rewriting one side.

## Decision

**Split by responsibility.**

| Step | Where | What |
| --- | --- | --- |
| Gather | Add-in, one coarse command | `geometry.candidates`: for a batch of requests (a feature ID with entity kinds, or a stored reference ID), return each candidate entity's persistent reference ID, entity type, signature (7.3) and adjacency, plus the owning feature's ID and type |
| Decide | Python (`cad-references`) | Apply role rules (5.7), signature matching and confidence scoring (7.4), and ambiguity handling. Pure functions over the gathered facts, so they are tested offline on recorded candidates (15.5) |
| Pin | Python | Store the decision as a persistent reference ID with the signature it matched. Plans (6.5), Resolved Schemes and drawing records hold only pinned IDs |
| Use | Add-in, inside the operation | Dereference the pinned ID (`GetObjectByPersistReference3`), re-check the stored signature within tolerance, and for drawings map the model entity into the target view (7.5). A missing entity is `REF_NOT_FOUND`, a signature mismatch `REF_SIGNATURE_MISMATCH`, and an entity that is not visible in the view or maps to several view entities is `REF_NOT_IN_VIEW`. Nothing is re-resolved silently |

**By phase.**
- **Phase 1b (stopgap).** At intake of a Drawing Intent, the core resolves every `feature.role`, `geo:` and `swdim:` reference through `geometry.candidates` and the role rules, and pins the result. `swdim:` names are converted to `ParamRef`s (5.8). Unresolvable or ambiguous references fail intake with `REF_*` errors listing the candidates (7.4).
- **Phase 1c.** The compiler's Geometry Resolver stage (6.2) does the same for Part Feature Graph references, through the injected backend port (guideline G2). Because the candidates are recorded with the plan, compiling the same bundle against the same recorded candidates gives the same plan (6.4).
- **Phase 2.** The full semantic reference system (section 7) replaces the stopgap rules behind the same split. Only Python's scoring changes, and the add-in command gains signature fields if needed (minor protocol version, ADR-042).

## Rationale

The add-in sees the model; Python holds the rules. Putting gathering in one coarse call respects ADR-032. Keeping every decision in Python keeps it deterministic, testable offline and replaceable in Phase 2 without touching C#. Re-checking signatures at execution catches a model that changed between compile and execute instead of attaching to the wrong entity.

## Consequences

- ADR-036 gains the `geometry.candidates` command.
- Plans and Resolved Schemes depend on the model state they were resolved against. Their keys include the part fingerprint (13.1), so a changed part forces re-resolution.
- Adds `REF_SIGNATURE_MISMATCH` and `REF_NOT_IN_VIEW` to the error catalogue (ADR-037).

## Where it applies

- [architecture/geometry-references.md](../architecture/geometry-references.md) — section 7.4, 7.5
- [architecture/cad-compiler.md](../architecture/cad-compiler.md) — section 6.2, 6.4
- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.1
- [architecture/backend-operations.md](../architecture/backend-operations.md) — section 6.5
- [ADR-032](ADR-032-python-owns-jobs.md), [ADR-036](ADR-036-ipc-protocol.md)
