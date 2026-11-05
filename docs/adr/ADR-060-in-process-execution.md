# ADR-060: Native execution stays in process; orchestration stays out of process

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, section 8.8.12. Reaffirms ADR-028 and adds the evidence that would reopen it

## Context

ADR-028 placed the C# executor in process, on the argument that cross-process COM is too slow. Its 1 ms per call figure is an estimate, and A1 has not measured it. A separate out-of-process execution service would isolate crashes and allow simpler debugging, so the question deserves recording with its evidence.

## Decision

Keep the split: Python compiler and jobs out of process, C# semantic adapter inside `SLDWORKS.exe`, coarse commands over a named pipe. Out-of-process COM stays for spikes and diagnostics only.

## Rationale

| Point | In process (chosen) | Separate COM service |
| --- | --- | --- |
| Per-entity reads | Direct | Marshalled. SOLIDWORKS documents out-of-process cost through `CommandInProgress`; a third-party source reports hundreds to thousands of times slower for many calls |
| STA thread | Native (8.3) | Requires its own marshalling discipline |
| Document events | Direct (8.6.5), needed for rule 13 | Available with more moving parts, and racier |
| Crash isolation | Python survives a SOLIDWORKS crash. An add-in fault can end SOLIDWORKS | Service survives, but SOLIDWORKS can still end: two out-of-process spike runs ended with SOLIDWORKS exiting, cause unproven |
| Debugging | Harder | Easier |

The key isolation the system needs is that jobs, journal and store survive a SOLIDWORKS crash, and the split already gives that.

## Consequences

- An add-in defect can harm an engineer's session, so ADR-059's entry-point rules and the leak test are mandatory, and a build needs SOLIDWORKS closed (DLL lock, known).
- Live runs must never use the owner's working session (HANDOFF rule).
- **Reopen this if any is shown:** add-in faults repeatedly end SOLIDWORKS while equivalent out-of-process calls do not; the A1 measurement shows out-of-process meets the section 16 targets for the operations in use, *and* events prove workable; or a required workflow cannot run in the engineer's session (A12).

## Where it applies

- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — section 8.8.12
- [ADR-028](ADR-028-in-process-solidworks-add-in.md), [ADR-032](ADR-032-python-owns-jobs.md), [ADR-041](ADR-041-core-service-topology.md)
