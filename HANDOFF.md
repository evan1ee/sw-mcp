# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Phase 0 contracts and the pure parts of Phase 1a. Nothing has run against SOLIDWORKS yet.
- **Spec:** v1.21, with one open item in the [register](docs/specifications/open-decisions.md): K3, which needs the owner's sheet format.
- **Branches:** milestones 1 and 2 are merged to `main` ([#1](https://github.com/evan1ee/sw-mcp/pull/1), [#2](https://github.com/evan1ee/sw-mcp/pull/2)). Milestone 3 is merged too ([#4](https://github.com/evan1ee/sw-mcp/pull/4)). Milestone 4 is in open PR [#5](https://github.com/evan1ee/sw-mcp/pull/5), branch `feat/ipc-contract`, not yet merged.
- **Verification on the branch:** generator check, ruff, pyright strict and lint-imports are clean; 1342 Python and 125 C# tests pass locally. See the PR for its CI result.
- **Built:**
  - `cad_ir.core`: IDs, references, quantization, canonical hashing, derived IDs, validation issues, schema validation.
  - `cad_ir.bundle`: bundle manifest validation.
  - `schemas/`: `common/v0.json`, `common/errors.json` (38 codes), `bundle/v1.json`, `drawing-geometry-snapshot/v0.json`, `drawing-report/v0.json`, `ipc/v0.json`, `ipc/ops/` (`document.open`, `document.close`), with fixtures in `tests/fixtures/schemas/`.
  - `scripts/generate_contracts.py`: embeds schemas and error codes in `cad_ir/generated/`, and generates IPC types for Python (`cad_ir.generated.ipc`) and C# (ADR-051).
  - `cad_drawing.checks`: D1, D2, D3, D5 (duplicates), D7, D8, D10, soft metrics and `build_report`, on snapshots.
  - `cad_protocol`: framing, `IpcClient`, `IpcBackend`, `replay_backend`; the `Backend` port in `cad_application.ports`.
  - `ExecutionServer.Core`: `FrameCodec`, `IpcSession`, `OperationLedger`.
  - `tests/fixtures/ipc/`: 15 hand-written transcripts, replayed against each side.
- **Reports cannot be `done` yet:** D4, D6, D9 and D5's auxiliary marking are `not_evaluated`, and `calibration.status` can only be `unverified`.
- **Not built:** D4, D6, D9, D5's auxiliary marking, the real named pipe and session discovery, the add-in and adapters, the store, jobs, MCP tools. All other packages and apps are scaffolds.

## Changes Made

- **Plans:** [shared IR core](docs/superpowers/plans/2026-11-03-shared-ir-core.md), [drawing geometry checks](docs/superpowers/plans/2026-11-04-drawing-geometry-checks.md), [drawing report and checks](docs/superpowers/plans/2026-11-04-drawing-report-checks.md), [IPC contract](docs/superpowers/plans/2026-11-04-ipc-contract.md). Their checkboxes were not ticked; all are complete.
- **Spec decisions:**
  - §3.4.8: schema `$id`s, annotations, `retryable` meanings, integer limits (owner-approved).
  - §11.5.1: snapshot encoding; checks run on the quantized snapshot; dimension, title-block and rebuild data.
  - §11.5.2: exact D1 chain and baseline exemption; chord error of epsilon/2; D7 rules.
  - §11.5.3 [Builder's call]: D5 has two parts, and closed chains count as duplicates; a drawing read back with no unsaved changes counts as surviving reopen, because `check_drawing` never saves.
  - §11.5.4 [Builder's call]: report contents and verdict rule.
  - §8.7 [Builder's call]: IPC errors, handshake order, `ops.apply` and `drawing.snapshot` shapes, ledger, cancellation, chunks, transcripts.
  - [ADR-051](docs/adr/ADR-051-contract-type-generator.md) [Builder's call]: own generator instead of `datamodel-code-generator`, which fails on the schemas. Changes ADR-035.
  - [ADR-052](docs/adr/ADR-052-csharp-json-library.md) [Builder's call]: `Newtonsoft.Json` in the add-in.
- **Owner decisions** ([ADR-050](docs/adr/ADR-050-phase-0-owner-decisions.md)): shared SOLIDWORKS session; `ISO 2768-m` with ISO 22081; note-based QA balloons; custom-property and `MarkedForDrawing` writes only by an explicit per-call option; no PDM.
- **New dependencies:** `rfc8785` and `jsonschema` in `cad-ir`; `Newtonsoft.Json` in `ExecutionServer.Core`; `coverlet.collector` in `ExecutionServer.Tests`.
- **GitHub settings:** repo is public; auto-merge is allowed; `main` requires `python` and `csharp-core`, with admins exempt.

## Next Steps

1. **Land milestone 4:** the owner reviews ADR-051, ADR-052 and §8.7, then merges [#5](https://github.com/evan1ee/sw-mcp/pull/5) once its checks pass. After merging, update the Branches line above.
2. **Sheet formats:** the owner confirms whether the untracked files in `standards/iso/templates/` are the company sheet formats, and how to read their fields (register K3).
3. **`check_drawing` and `get_drawing_report`:** project store, job journal and MCP tools, tested over replayed transcripts. This needs the client on a real transport, with session discovery and a heartbeat (out of scope in the IPC plan). `IpcClient` is single-threaded, so the heartbeat will need a reader thread. Add report warnings for draft-view switches and newer service packs (out of scope in the plan).
4. **Phase 0 work on the SOLIDWORKS machine:** create `docs/specifications/assumptions.md` and prove A1–A17; run the reference study; calibrate the check thresholds on approved drawings (§11.5.2).

## Known Issues

- **Needed from the owner:** company sheet format and title-block mapping (`standards/iso/templates/` has three untracked files dated 2015–2018, not yet confirmed or committed: `a3 - EPG_Plastic_Rev0.slddrt`, `a3 - EPG_Steel_Rev0.slddrt`, `ISO-mm.prtdot`; the last has no LFS rule). D8 is tested only with a synthetic mapping and cannot run on a real drawing without them (register K3); benchmark parts and reference drawings; holdout parts (§11.8). ADR-034 to ADR-049 are still Proposed.
- **`ExecutionServer.Core` is unproven inside SOLIDWORKS:** no pipe host or add-in exists, and `Newtonsoft.Json` loading in `SLDWORKS.exe` is unproven (A17). Transcripts are hand-written, so they show the two sides agree with the spec, not with real SOLIDWORKS.
- **Two remotes have diverged:** Gitea's `origin/main` is `9dce10e`, with the same files as GitHub's `main` but different commits. Each sync needs a merge commit; never force-push. Local `main` tracks `github/main`, and CI runs only on GitHub.
- **Auto-merge:** GitHub refuses to arm it on a PR whose checks have already passed, so such a PR is merged directly.
- **Stacked PRs:** retarget the upper PR to `main` after the lower one merges, otherwise its commits never reach `main`.
- **Self-hosted runner risk:** the repo is public, so a fork PR could run code on a self-hosted SOLIDWORKS runner. Restrict those jobs before adding the runner, or make the repo private.
- **D5 limits until a Resolved Scheme exists:** a chain spread across views, or a reference dimension repeating a parameter in another view, is missed (§11.5.3).
- **Unverified:** all drawing checks have run only on synthetic snapshots, never on real SOLIDWORKS data, and every report says so. The API calls behind the new snapshot fields are unproven (A15, A16).
