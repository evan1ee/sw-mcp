# ADR-064: Per-operation verification contracts derived from the IR

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.32, sections 6.5.3, 8.4.1, 8.8.6, 8.9.6, 10.2; [verifiable compilation gap analysis](../superpowers/review/2026-11-05-verifiable-compilation-gap-analysis.md), findings V1, V2, V8, V9, V10. Extends ADR-007 and ADR-063

## Context

ADR-063 fixes where judgement lives, and keeps execution, rebuild and verification as separate outcomes. It does not say how one feature is checked before the next one is built. Today:

- A plan's `postconditions` are bare names such as `rebuild_ok`, with no expected values, and no evaluator exists.
- An operation's result holds `native_id`, `feature_id` and `status`. It cannot show a rebuild state, a depth or a parent.
- A feature's definition is not read until roadmap phase A3, so a wrong depth is found only at the final check, if it is found at all, and nothing observed says which feature caused it (10.4).
- The accepted statuses are `passed`, `failed` and `not_evaluated`. Warning, Not Applicable, Not Executed and Unsupported cannot be told apart.
- A failed postcondition has no error code, and the failure stage is not recorded.

Deterministic planning does not make geometry deterministic (8.8.7), so each built feature has to be checked against what the IR asked for.

## Decision

**1. Contracts come from the IR, through `cad-verification`.** A pure `feature_contracts(graph)` gives each node a contract of required and optional checks, with expected values and tolerances. The compiler never computes them, and the plan carries no expected values. A plan's `postconditions` still name what applies, and the job joins a contract to an operation through `source`. The contract's hash is recorded in the evidence.

**2. Every operation is judged before the next one is sent.** The sequence is:

1. Journal `batch_sent`, then send one operation.
2. The handler returns its result with an additive `observation`, read back in the same command.
3. Journal `op_result`.
4. A pure `evaluate(contract, observation)` judges it in the core.
5. Journal `op_verified`.
6. Continue only if every required check passed.

**3. Fail fast.** A required check that is `failed` or `not_evaluated` ends the job. Later operations stay `not_attempted`, and `depends_on` is used only to record `blocked_by` in evidence. There is no partial continuation or scheduler.

**4. Observation is tiered by cost.**

| Tier | When | Facts |
| --- | --- | --- |
| T0 | Every operation | Feature ID and type, error code and warning flag, suppression, direct parents, sketch entity count, document update stamp |
| T1 | Every solid feature, once K15 clears them | Feature parameters (depth, end condition), rebuild-needed state, solid body count |
| T2 | Verification points, off by default until K18 is measured | Volume change against the IR |
| T3 | Final only (10.2.1) | Full measurement, in session and after reopen |

Full-model measurement after each feature is never required.

**5. Observers never call a native method that changes document state to read it.** `IExtrudeFeatureData2.AccessSelections` and its equivalents are excluded, because the API puts the model into a rollback state.

**6. Check status gains two values.** This extends ADR-063's status list. It keeps ADR-063's rule that `not_evaluated` never counts as passed.

| Situation | `status` | `reason` | Effect on a required check |
| --- | --- | --- | --- |
| Passed | `passed` | | Continues |
| Failed | `failed` | | Ends the job |
| Native warning | `warning` | | Ends the job in the MVP (owner decision, closes K22). A reviewed list of harmless warnings may be allowed later |
| Does not apply | `not_applicable` | Required | Ignored in rollup. Decided from the IR alone, never by the backend, so a check cannot excuse itself |
| Never ran | `not_evaluated` | `not_executed` | Ends the job |
| Backend cannot do it | `not_evaluated` | `unsupported` | Ends the job, unless the contract marks the check optional |
| Data absent or malformed | `not_evaluated` | `missing_data`, `malformed_data` | Ends the job |

**7. Failures are classified.** Evidence gains `outcome.failure_class`:

| Class | Stage | Code |
| --- | --- | --- |
| `compilation` | VALIDATED | `COMPILE_FAILED` |
| `execution` | EXECUTING, operation error | `BACKEND_REBUILD_ERROR`, `BACKEND_OPERATION_FAILED` |
| `feature_verification` | EXECUTING, contract failed | `FEATURE_VERIFICATION_FAILED`, with `details.node` and `details.checks` |
| `final_verification` | VERIFYING | `PART_VERIFICATION_FAILED` |

**8. Each contract states its level.** `level` is `exact`, `bounded`, `declared` or `structural`, as K16 recommends. Only `exact` is used until K16 is decided, so a later feature cannot look verified on weaker evidence.

## Rationale

**Contract derived from the IR, against expected values in the plan.** If lowering wrote both the parameter and its expected value, a lowering error would agree with itself. The seeded defect in 8.9.10, a plan depth of 9 mm against a graph depth of 10 mm, could not be caught. Keeping plans free of expected values also leaves them byte-identical, and needs no IR schema change.

**Observation in the same command, against a separate inspect command.** A separate command adds a round trip per feature and leaves a gap in which an engineer could edit the document. Stage 4 of 8.8.6 already reads back, and ADR-032 asks for coarse commands.

**Fail fast, against continuing with independent branches.** Plans run in sequence, a batch already stops at its first failure, and a working file with unknown contents is never repaired (8.8.8). A scheduler would add risk and give no better result.

**Tiers, against full measurement after each feature.** Most errors at this stage show up in cheap facts, and the final check still measures everything. T2 exists because a feature can be healthy and still remove nothing. It stays off until its cost is measured.

**Extending the status list, against six flat statuses.** One non-verdict with a reason keeps ADR-063's rule simple to enforce. Only the job's rollup has to know about `not_applicable` and `warning`.

## Consequences

- **Easier:** a failure names its node and check, and every comparison runs offline on recorded observations. Evidence becomes a true projection of the journal, because `op_verified` holds what recovery needs.
- **Harder:** each new feature type ships a contract rule as well as a handler, translator and observer. Each observation adds native reads to every operation, at a cost not yet measured (K18).
- **Honest gap until K15 closes:** parameter checks stay optional and report `not_evaluated` with `unsupported`. Until then a parameter error is caught only by the final geometry checks, and a parameter error with no measured effect is not caught.
- **Additive schema work,** folded into roadmap A0:
  - `VerificationContract` and check results in `schemas/execution-evidence/v0.json`, with no new schema folder.
  - `observation` on `sketch.create` and `feature.create` results.
  - `schemas/ipc/ops/document.rebuild.json`.
  - An `op_verified` journal record.
  - One error code.
- **Not additive:** `dir` leaves `feature.create` (8.9.3 rule 4). Nothing consumes it yet.
- **Code to change:** `CheckResult.status` in `cad_verification/part.py` has three values today, and gains the two new ones.
- **Decided elsewhere:** K19 settles what rebuild state means on a reopened document. K15 settles which parameter reads are safe.
- **Unchanged:** ADR-057's drawing freeze, because this applies to `plan` jobs only. The drawing report's `pass`, `fail`, `not_evaluated` vocabulary stays until the freeze lifts.

## Where it applies

Applied in specification v1.32. Schemas follow it from v1.34 (roadmap A0). Code follows in roadmap A2 and MVP Tasks 8 to 9b.

- [architecture/backend-operations.md](../architecture/backend-operations.md) — sections 6.5.2, 6.5.3
- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — section 8.8.9
- [architecture/execution-engine.md](../architecture/execution-engine.md) — sections 8.4.1, 8.7
- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — sections 8.9.3 to 8.9.6
- [architecture/verification-engine.md](../architecture/verification-engine.md) — sections 10.2.1, 10.2.2
- [architecture/project-store.md](../architecture/project-store.md) — section 13.2.3
