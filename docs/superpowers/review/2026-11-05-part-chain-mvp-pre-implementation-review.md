# Part Chain MVP: Pre-Implementation Architecture Review

**Date:** 2026-11-05
**Reviewed:** the [MVP design](../specs/2026-11-05-part-chain-mvp-design.md) and [implementation plan](../plans/2026-11-05-part-chain-mvp.md) against the repository on branch `feat/part-chain-mvp`, specification v1.29 and the ADRs.
**Status:** Findings for owner review. The changes in this review were applied to the design and plan on 2026-11-05, and the owner approved the recommended option for each of D1 to D5 the same day. Implementation has not started, and SOLIDWORKS behaviour is still unverified.

**Recommendation: CONDITIONAL GO.** The architecture is sound, but implementation shouldn't go past the spec task until the plan and design are patched.

The review read the code, spec and ADRs, but ran no tests and changed no files. **Confirmed** means it was seen in the code or documents. **Investigate** means only a live run can settle it.

## 1. Executive assessment

**Decisions to keep:**

- The IR → compiler → plan → job layering, with a pure core
- One operation per batch, with symbols bound by the job
- Working-file publication with a no-replace rename
- Expected values computed from the IR, plus verification after reopen
- The narrow first feature set

The design and plan were written by the same author as this review, so these faults are that author's. The main ones:

- Verification can pass the wrong part.
- The ownership rule doesn't deliver the safety the design claims.
- Recovery can't see publication.
- Rule 13 of the spec isn't met in the current add-in.

Two requested focus points turned out differently from what might be expected:

- **`RefPlane` order is not a spec violation.** Section 5.3.6 explicitly specifies identifying planes by order, so it only needs a safety check.
- **Raw JSON compiler input matches 6.7.2.** The real problem is that the job carries the graph in two forms (F5).

## 2. Critical findings

### F1 (Critical): verification can pass the wrong part. Confirmed by design review.

- **Where:** design 9; plan Task 5; `part.measure` in design 7.
- **Problem:** the checks are body count, bounding box, volume and feature list. Holes at (±20, ±10) instead of (±40, ±20), or a differently shaped profile with the same area and box, pass all of them. A lowering bug that moves geometry could therefore publish as "verified". Section 10.2 already lists hole positions and centre of mass under geometry.
- **Change:**
  - Add center of mass to `part.measure`.
  - Add a list of cylindrical faces (axis point, direction, radius), and compare it with the IR's circles.
  - Add surface area.
  - Add seeded tests for moved holes and a same-area profile.
- **Must change:** design, plan, spec 10.2.

### F2 (Critical): the ownership rule leaves custody gaps. Confirmed, except where noted.

- **Where:** design 7; plan Task 7; [`DrawingCreationAdapter.cs:199`](../../../apps/execution-server/ExecutionServer.Adapters/Drawings/DrawingCreationAdapter.cs); [`DocumentEventMonitor.cs:61`](../../../apps/execution-server/ExecutionServer.AddIn/Events/DocumentEventMonitor.cs).
- **Problems:**
  - `CloseUnlisted_Allowed` means a core bug can still close an engineer's unlisted part, which contradicts the design's stated reason for the table.
  - `document.save` accepts a `target_path` and calls `SaveAs4` with the silent option, so an owned part could be saved over another file. Whether it overwrites is to be confirmed in the spike.
  - `part.create` has the same exposure unless it refuses an existing file.
  - `DestroyNotify` is not subscribed anywhere. The add-in only listens to `ActiveDocChangeNotify` and `FileCloseNotify`, so the planned `Forget` has no trigger, and `ForgetDocument` still has no caller.
  - Borrowed entries are never removed, because the add-in receives no job-end signal.
  - The table is keyed by path alone, while F39 of the architecture review requires instance and path to stay separate.
- **Change:**
  - Refuse save and close on any `.SLDPRT` unless this job owns it. Keep today's behaviour for drawings.
  - For parts, refuse a `target_path` that differs from the document's path, and refuse `part.create` if the file exists.
  - Key entries by path and job ID, and only ever match the requesting job.
  - Use `FileCloseNotify` for `Forget` and the ledger, after the spike confirms its `docName` form.
  - Return an add-in-issued `instance_id` from `part.create` and `document.open`, and have `part.measure` report it.
- **Must change:** design, plan, ADR-046 and ADR-032 wording.

## 3. Detailed findings by severity

### High

#### F3: crash recovery can't see publication. Confirmed.

- **Where:** [`journal.py:92`](../../../packages/cad-application/src/cad_application/store/journal.py), [`journal_records.py:139`](../../../packages/cad-application/src/cad_application/store/journal_records.py), design 8.
- **Problem:**
  - A crash after the rename leaves a file at the target, a job marked FAILED, no part record, and retries refused.
  - `check_drawing` records `document open` only after the response, so copying it means a crash during `part.create` never lists the document.
  - `_action` silently turns any unknown action into `open`, so adding a new action without updating it corrupts recovery.
- **Change:**
  - Write `document` `create` before sending `part.create`.
  - Write `publish_intent` (path, fingerprint) before the rename and `published` after.
  - Update `_action`, the schema enum and recovery together.
  - On recovery, report a matching target as `published_unconfirmed`. Never adopt it silently.
- **Must change:** plan Task 9, spec 13.2.3, store schema.

#### F4: rule 13 of the spec is not met, and active-document needs are unspecified. Confirmed, except the API behaviour.

- **Where:** [`execution-engine.md:47`](../../architecture/execution-engine.md), add-in event monitor, design 7.
- **Problem:**
  - The add-in has no save or edit events and no regen subscription, so an engineer's changes to the working part go unnoticed. Reopen verification limits the damage but doesn't meet the rule.
  - An engineer switching the active document produces an event for the *other* document, which `_foreign_event` ignores.
  - The Stop banner doesn't exist: there are no matches in the add-in code.
  - "Never `ActiveDoc`" fixes addressing, but sketch and feature APIs may still need the document active. **Investigate.**
- **Change:**
  - Add a spike question on active-document requirements.
  - If they do need it, each part operation checks the active document and fails with `EXEC_INTERRUPTED_BY_USER`, rather than switching it back without saying so.
  - Subscribe to regen, save and destroy events on the working part's document.
  - The banner is decision D1.
- **Must change:** design, plan Tasks 1, 7 and 8, possibly ADR-050 by an exception.

#### F5: the job carries the graph twice and the compiler input is incomplete. Confirmed.

- **Where:** plan Tasks 4 and 9; 6.5.3; 6.7.2.
- **Problem:**
  - `PlanSpec` holds both `graph` and `graph_ref`, so they can differ.
  - `compile_part(graph_doc, ref, ctx)` has no pinned bundle, though 6.5.3 requires one in the plan.
  - The store sets `revision`, so whether the input includes it affects the hash.
- **Change:**
  - Use `PlanSpec(authorized, target_path, ref)`, with the job loading the stored revision.
  - Use `compile_bundle(CompileInput(manifest, documents), ctx)`. The parser stage keeps raw input as 6.7.2 says, and everything after it uses `PartGraph`.
  - Exclude `revision` from content the plan depends on, and record it as the pinned reference.
  - Keep `job.json` holding only the reference, not the whole graph.
- **Must change:** plan.

#### F6: the reopen and publish steps don't prove what they claim. Confirmed as a design gap.

- **Where:** design 8; plan Task 9; [`paths.py:126`](../../../packages/cad-application/src/cad_application/paths.py).
- **Problem:**
  - Nothing proves the reopen read from disk; SOLIDWORKS could return a document still in memory.
  - Nothing proves the published bytes are what was measured.
  - The folder could be swapped between authorization and rename.
  - Cancel boundaries aren't defined for this job.
- **Change:**
  - After close, require that the document is no longer open.
  - Require a new `instance_id` on reopen.
  - Take a fingerprint before reopen and again just before rename; they must match.
  - Re-run the path checks just before rename.
  - Add a cancel boundary: once the rename starts, the job ends COMMITTED.
- **Good news:** `os.rename` already gives the no-replace behaviour, as `write_new` relies on.
- **Must change:** design, plan, spec 8.4.

#### F7: connection closing is incomplete. Confirmed, except the reconnect gap.

- **Where:** [`discovery.py:186`](../../../apps/core-service/src/core_service/discovery.py), [`reconcile.py:26`](../../../apps/core-service/src/core_service/reconcile.py), engine `run_next`.
- **Problem:**
  - A failed handshake leaves the client open.
  - A failed `reconcile` leaks the backend, though its docstring promises a retry.
  - Closing in `run_next` affects `check_drawing` too.
  - The add-in creates one server instance at a time, so an immediate reconnect may fail with something other than "pipe busy", which is the only error the transport retries. **Investigate.**
- **Change:**
  - Close in both failure paths.
  - Close after the final state, and make any close failure a logged warning that never changes the outcome.
  - Add a bounded reconnect wait, plus a test with two rapid jobs.
- **Must change:** plan Tasks 6 and 9.

#### F8: the feature ID fallback conflicts with the spec. Confirmed.

- **Where:** design 7; [`part-feature-graph-ir.md:89`](../../architecture/part-feature-graph-ir.md).
- **Problem:** the design falls back to "type and order", but 5.3.6 says "never by display name or tree position" and names `GetPersistReference3` as the fallback.
- **Change:** use the specified fallback, and ask the spike to test it as well.
- **Must change:** design.

#### F9: front-end replacement breaks a test the plan doesn't list. Confirmed.

- **Where:** plan Task 11; `apps/mcp-server/tests/test_mcp_front_end.py`, `server/__init__.py`.
- **Problem:** these use `McpServer` and `handle_message`. Hidden drawing tools also remain callable, because `registry.call` doesn't check toolsets.
- **Change:**
  - Add these files to Task 11.
  - Enforce toolsets in the core's tool path for MCP calls, while in-process drawing tests set their toolsets explicitly.
  - Update the default in [`merge.py:198`](../../../packages/cad-application/src/cad_application/config/merge.py) and [`settings.py:39`](../../../packages/cad-application/src/cad_application/config/settings.py).
- **Must change:** plan, design 10.

### Medium

| ID | Where | Problem | Change | Must change |
| --- | --- | --- | --- | --- |
| F10 | Design 7, 5.3.6 | Plane order is specified, but a template may reorder or rotate planes. The bounding box would catch most cases, but with a late, unclear failure. **Investigate.** | Keep order, then check each plane's normal against its role and fail clearly | Design, plan Task 8 |
| F11 | Plan Tasks 4 and 9 | `CapabilityProfile` takes its hash from outside, is built in another package, and leaves out coverage. `SwAddin.cs:129` hard-codes `en-US`, so the profile misreports the UI language | Put `CapabilityProfile.from_session(HelloResult)` in `cad-compiler`, which `cad_ir` types allow without a dependency problem. Report the real language | Plan |
| F12 | Plan Task 9, 6.7.4, 13.2.1 | The same plan built twice has the same hash, and `write_new` raises on the second write. 6.7.4 and 13.2.1 also key plans differently | Reuse an existing plan and record that in provenance. Settle the key in Task 2 | Plan, spec |
| F13 | Plan Task 4 | The plan lists `plane_axes` as an input to the compiler, so lowering and expected values could share a bug | Lowering sends 2D coordinates only; remove it from Task 4 | Plan |
| F14 | Plan Task 8, `PartUnits` | The same conversion used for building and measuring could hide a wrong factor | Pin literal values in tests, and return raw SI values in `part.measure` with the core converting them | Design, plan |
| F15 | Plan Tasks 7 and 12 | `DispatchTests` can't reach `SwAddin`, because the test project references only `Core`. `test_wrong_plan_fails` can't inject a bad plan through `call_tool` | Move dispatch into `Core`. Add a test-only provider that alters the depth in transit | Plan |
| F16 | Plan Task 2, 12.4.2, 3.4.5 | "Identical document reuses its revision" isn't in 3.4.5, and `apply_part_graph` has no `expected_revision`, although 12.4.2 requires it on tools that change store documents | State the rule explicitly: creating needs none, and a changed graph without it fails with `REV_CONFLICT` | Spec |
| F17 | Design 9, `part.create` | "Every expected feature is present" allows extras, and the default template isn't recorded, so a template containing features changes the result | Require an exact solid feature match. Record the template path and hash in `part_result` | Design, plan |
| F18 | Design 5 and 8, 8.3 rule 11 | When rebuild runs, selection marks, `EnableGraphicsUpdate`, and `SettingsGuard` scope are all unspecified. `Execute` restores settings after every operation | Force a rebuild before save and none after a read-only reopen. Spell out rule 11 in Task 8 and restore everything in `finally` | Design, plan |
| F19 | Design 8 | A long target name passes authorization, then fails at `part.create` because the working name adds about 44 characters. `authorize` also returns `in_vault`, which the tool must act on | Check the working path length and vault status in the tool | Plan Task 10 |
| F20 | Plan order | Task 4 needs the operation schemas from Task 6, and A14 is tested only in Task 12, after everything depends on it | See section 6 | Plan |
| F21 | Baseline | Frozen drawing live tests haven't been re-run since the freeze, so a later failure couldn't be attributed | Run them first as a recorded baseline | Plan |

### Low

| ID | Where | Problem | Change | Must change |
| --- | --- | --- | --- | --- |
| F22 | Unicode | `ntpath.normcase` and `OrdinalIgnoreCase` could differ on rare characters, though not on Chinese. Review Focus 1 promises a pipe test, but Task 7 tests only the table | Add a Python-to-C# framing transcript, and confirm the SDK reads stdio as UTF-8. **Investigate.** | Plan |
| F23 | `rename_new` | The rename isn't flushed to disk, so a power loss could lose it after COMMITTED | Use `MoveFileExW` with write-through | Plan |
| F24 | Design 6.5.1 | `sketch.create` takes `plane:front`, while 6.5.1 says geometry uses pinned IDs. Standard planes are role references | Note the exception in 6.5.2 | Spec |

## 4. Drawing regression risks

| Shared change | Risk | Guard |
| --- | --- | --- |
| `document.save` and `close` addressing | Live tests pass `created_doc` from `drawing.create` and use `target_path` ([`test_live_view_pipeline.py:186`](../../../tests/live/test_live_view_pipeline.py)), so requiring real paths could break them | Keep today's lookup for drawings, and apply new rules only to `.SLDPRT` |
| `document.open` honouring `read_only` and reporting true `owned` | Changes `check_drawing` on live files, and may affect its in-memory rebuild (A16) | Run smoke live, before and after |
| Unknown operation becomes an error | All 13 advertised operations have branches, so this looks safe | Compare the list in a test |
| `Backend` gains `measure_part` and `close` | Fakes, replay and test doubles must follow | Keep existing transcripts unchanged |
| Engine closes the backend | Now also applies to `check_drawing` | Job rig test with two jobs |
| `JobEntry`, `JobHandle`, `new_job_record` | Currently typed to `CheckDrawingSpec` | Keep the positional record stable and add fields with defaults |
| `JobRecord`, journal records, store schema | Older `job.json` files must still load | Lenient-reader test on a v0 record |
| `authorize` gains `new_file` | Default behaviour must not change | Keep existing path tests |
| `errors.json` and generated files | Exact catalogue and retry-class tests | Update the expected list only |
| Toolset default | Tests expecting `check_drawing` listed | Set the toolset explicitly in those tests |
| `get_execution_status` schema | Additive only | Keep existing contract examples unchanged |
| Pipe host ACL and token handling | Could break front-end connection | Real-process test |

No frozen file needs an edit under these rules. The plan should say that if one does, work stops and it comes back to the owner.

## 5. Missing requirements and tests

**Unit and contract:**

- Moved holes, and a same-area profile with the same box
- Extra feature rejected
- Repeated plan reuse
- A v0 `job.json` still loading
- Ownership refusals for `.SLDPRT` close and for a mismatched `target_path`
- A toolset-disabled tool being refused over MCP
- A long working path being rejected

**Integration and failure recovery:** simulate a crash at each of these points:

- Before and after `part.create`
- After each operation
- After `publish_intent`
- After the rename
- Before COMMITTED

Also test:

- Cancel just before the rename
- A failed handshake and a failed reconcile both closing the connection
- Two rapid jobs reconnecting

**Live:**

- The engineer switches, edits, saves or closes the working document during a job
- Reopen returning a genuinely new instance
- A template with reordered planes or extra features
- `taskkill` on the core mid-job, followed by a clean next job
- A Chinese path through the full chain, not just the table

**Investigate in the spike (all still unverified):**

- `SaveAs4` overwrite behaviour
- Active-document needs
- `FileCloseNotify` name format
- A reopen reading from disk
- The reconnect gap
- `GetPersistReference3` stability

## 6. Recommended plan changes and revised sequence

1. **Add Task 0:** record a live drawing baseline. Needs SOLIDWORKS with the current add-in.
2. **Extend Task 1:** add the spike questions above, and move the A14 load test here, against the current add-in.
3. **Move Task 6 before the compiler,** so plans are checked against real operation schemas.
4. **Split Task 7:** dispatch extraction and ownership, then events and instance IDs.
5. **Split Task 9:** store, journal and recovery first, then the job.
6. **Apply each finding's change** to the task it names.

```text
T0 Baseline ─► T1 Spike and A14 ─► T2 Spec v1.30 ─► T3 IR ─► T6 IPC contracts
                                                               │
                             ┌─────────────────────────────────┤
                             ▼                                 ▼
                    T4 Compiler + T5 Verification       T7a Dispatch, ownership
                             │                                 ▼
                             │                          T7b Events, instance IDs
                             │                                 ▼
                             │                          T8 Part adapters
                             ▼                                 │
                    T9a Store, journal, recovery               │
                             ▼                                 │
                    T9b Plan job ◄─────────────────────────────┘
                             ▼
                    T10 Tools ─► T11 Runtime ─► T12 Live ─► T13 Run from Claude
```

T4/T5 and T7a–T8 can run in parallel. T9b needs fakes from T6 and real behaviour only by T12, and T8 must be done before T12.

## 7. Decisions needing the owner's approval

**D1. Stop banner (rule 13, ADR-050 is an Accepted owner decision).** Build it in this MVP, or record a temporary exception? Recommended: the exception, limited to the MVP, with `cancel_execution` as the way to stop. The event detection in F4 still gets built.

**D2. Stronger verification.** Adding cylinder, center-of-mass and area checks enlarges `part.measure`. Recommended: yes, since F1 is otherwise a false "verified".

**D3. Design section 14 calls,** still needing an explicit yes:

- Fixed-coordinate, non-parametric sketches
- The plate as first part
- Tolerances of ±0.01 mm and ±0.01%
- Drawing tools hidden and refused by default

**D4. Where working and failed files live:** beside the target, as designed, or in the project's `.cad` folder, which is tidier but makes failures less visible. Recommended: beside the target.

**D5. Stricter part rules (F2).** Refusing to close any unowned `.SLDPRT` is safer, but a part job can then never tidy up after itself in an unknown state. Recommended: yes.

## Recommendation: CONDITIONAL GO

**Can start now:** Task 0 and the extended Task 1, since they only touch scratch files and change no product code.

**Required before Task 3:**

- Design and plan patched for F1–F9
- D1–D5 decided
- Spike results recorded, with any failed assumption brought back to the owner

**Required before Task 12:** the crash-point tests from F3 passing.
