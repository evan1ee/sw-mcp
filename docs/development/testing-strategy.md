# 15. Testing Strategy

> Specification v1.20, section 15. Index and section map: [specifications/README.md](../specifications/README.md).

## 15.1 Unit (no SOLIDWORKS)

IR parsing, schema and semantic validation, graph analysis, cycle detection, topological sort, graph diff, parameter evaluation, lowering, plan generation, reference matching, **drawing check geometry (D1–D5 intersection and overlap logic on recorded Drawing Geometry Snapshots, 11.5.1), duplicate/completeness logic (parameter coverage and geometric determinacy), placement engine decisions, pinned-annotation handling, planned vs as-built layout diff and pin detection, dimension scheme regeneration (authored entries kept), IR bundle validation and composition rules (3.3: declared dependencies, references into absent modules rejected, fallbacks when an owner is absent, change ripple to dependents only), assembly graph validation (mate targets, hierarchy), language-independent feature and plane identification, job lifecycle and journal recovery after a crash on either side (8.2, 8.4), Resolved Scheme ID stability across regeneration (11.10.1), document identity by fingerprint and the lost-state pin rule (13.1)**.

## 15.2 Integration (live SOLIDWORKS)

COM connection, documents, sketches, features, rebuild, save/reopen, geometry inspection, persistent references, error handling, **drawing creation, model-item insertion, annotation read-back, title block fill**, configurations, and a non-English SOLIDWORKS install (at least one localized UI language, to prove 5.3.6).

**Environment.** Live suites need a dedicated Windows machine with a SOLIDWORKS 2025+ license, a logged-in interactive desktop session and a visible SOLIDWORKS (8.3). They cannot run as a service or on a headless CI agent. The CI runner on that machine runs as the logged-in user.

**Version matrix.** Annotation and drawing behavior changes between service packs. The supported versions are pinned to exact service packs (for example 2025 SP5 and the current 2026 SP), and the live suites and the drawing benchmark run on each. Supporting a new service pack means passing the benchmark on it first.

## 15.3 End-to-End

End-to-end tests follow task composition (3.3): each test submits only the modules its task uses.

```
Request → IR bundle (Part Feature Graph [+ Assembly Graph] [+ Design Intent] [+ Drawing Intent + Drawing Layout])
        → Compiler → Execution Plan → SOLIDWORKS → Verification
        → Drawing pipeline → Drawing checks → Final documents   (drawing tasks only)
```

At least one test per row of the task-composition table in 3.3.

## 15.4 Benchmarks

- **Drawing benchmark (P0):** section 11.8.
- **CAD benchmark (P1):** at least 30 models with expected geometry and feature-history criteria:
  - Basic: box, cylinder, sphere, hollow cylinder, stepped shaft.
  - Mechanical: bracket, flange, gear, spring, pulley, bearing housing.
  - Assembly (Phase 2): two-part concentric/coincident mates, a subassembly, an ambiguous mate target that must fail, a slider with a limit mate (subset of the spring-driven injector).
  - Molded: housing, boss, rib, snap-fit, thin-wall enclosure, drafted part.
  - Complex: loft, sweep, pattern, multi-body, shell with fillets.
  - Editing: change upstream dimension, delete upstream feature, change sketch, rebuild after topology change, resolve references after modification.

## 15.5 Contract tests

Three contracts join code written separately in Python and C#: the MCP tool contracts (12.4), the add-in and core-service protocols (ADR-036, ADR-041), and the IR and artifact schemas (3.4, ADR-035). Contract tests check each side against the contract, not against the other side, so both can be built and changed independently. They need no SOLIDWORKS and run in hosted CI (ADR-039).

| Contract | Tests |
| --- | --- |
| Schemas | Each schema has `valid/` and `invalid/` fixtures in `tests/fixtures/schemas/<name>/`, including every JSON example in this specification (3.4.6). Both the generated Python models and the generated C# types (ADR-035) must accept every valid fixture and reject every invalid one, with the expected error code and pointer (3.4.7) |
| Compatibility | The CI contract diff (ADR-042), and every migration from the previous major run over that major's fixtures |
| MCP tools | For every contract file: the generated tool definition matches a committed snapshot; each `examples` call validates against `input` and its response against the envelope and `output`; a handler returning an error code not in `errors` fails; the one-line text summary stays under 200 characters (ADR-044); token budgets (12.3); no name equals a reference tool (12.1) |
| Add-in protocol | Recorded transcripts in `tests/fixtures/ipc/` (one JSON Lines file per scenario: each frame with direction and timing). The Python client is tested by replaying the add-in's side to it. C# `Core` is tested by replaying the core's requests and comparing its responses, with timestamps and IDs masked |
| Core-service protocol | The same transcript format, for front-end ↔ core scenarios: two front-ends sharing a queue, a front-end leaving mid-job, version skew (ADR-041) |

**Keeping fixtures honest.** Every live-suite run (15.2) records fresh transcripts and snapshots for its scenarios. A pull request that changes recorded fixtures shows the diff for review like code. A fixture older than the oldest supported SOLIDWORKS version (ADR-045) is re-recorded or removed.

## 15.6 Test policy

- **No automatic retries** in any suite. A retry hides exactly the nondeterminism that 6.4 and 11.11 forbid.
- **Flaky tests are quarantined, not ignored.** A test that fails intermittently moves to a quarantine list with an issue and an owner. After 14 days in quarantine it fails the build again until it is fixed or deleted.
- **Determinism tests.** The compiler, view planning and the placement engine run twice on the same inputs in the same process and once in a fresh process. The canonical hashes (3.4.4) of their outputs must match.
- **Live-suite isolation.** Each live test opens its own copies of benchmark files from a clean working folder, runs in a SOLIDWORKS session with the add-in's settings guard active (8.6.4), and checks after itself that every preference was restored and no document was left open.
- **Coverage.** 80% line coverage on `packages/` (ADR-034) and on C# `Core` (ADR-038), measured in hosted CI. Adapters are covered by the live suites, which report which adapter operations they exercised.
