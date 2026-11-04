# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Phase 0 contracts, IPC framing/transcripts, project store, job journal, job engine, Phase 1a tool handlers (`check_drawing`, `get_drawing_report`, `get_execution_status`, `cancel_execution`), and `core-service` composition root. Nothing has run against SOLIDWORKS yet.
- **Spec:** v1.23, with open items in the [register](docs/specifications/open-decisions.md): K3 (sheet format field mapping), J11 (draft-view switched indicator in snapshot), and J21 (C# transcript harness scripting an error response). Catalogue has 40 codes.
- **Branches:** milestones 1, 2, 3, 4, and 5 are merged to `main` ([#1](https://github.com/evan1ee/sw-mcp/pull/1), [#2](https://github.com/evan1ee/sw-mcp/pull/2), [#4](https://github.com/evan1ee/sw-mcp/pull/4), [#5](https://github.com/evan1ee/sw-mcp/pull/5), [#6](https://github.com/evan1ee/sw-mcp/pull/6)).
- **Verification on main:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly.
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly (333 files).
  - `uv run pyright` passes (0 errors, 0 warnings).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest` passes (2352 passed in 36.8s).
  - Test coverage on `packages/cad-application` and `apps/core-service` is 96.06% (763 tests; ≥ 80% required).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (127 passed, 0 failed).
  - `git status --short standards/` is empty.
- **Built:**
  - `schemas/`: store (`store/v0.json`), configuration (`config/v1.json`, `config/title-block/v1.json`), MCP contract meta-schema (`mcp/contract/v0.json`), Phase 1a tool contracts (`mcp/check_drawing.json`, `get_drawing_report.json`, `get_execution_status.json`, `cancel_execution.json`), common errors (40 codes, including `FILE_NOT_FOUND` and `STORE_UNAVAILABLE`).
  - `cad_application.store`: `FileStore`, `StoreSet`, atomic writes, journal records and state transitions (8.4), crash recovery (13.2.3), and retention clean-up (13.2.4).
  - `cad_application.jobs`: `JobEngine` (thread-safe, synchronous per ADR-053), `check_drawing` job runner, job views, cancel handling, notification dispatch.
  - `cad_application.tools`: `ToolRegistry`, contracts loader, argument validation against embedded JSON schemas, pagination cursors (12.4.2), tool summary builders.
  - `core_service`: `CoreService` composition root, `OsFileSystem` with OS file locks (`msvcrt`), `SystemClock`, `SystemIdSource`, `JsonlEventLog` (G3 allow-list), `ReplayBackendProvider`.
  - `tests/fixtures/ipc/`: 7 `check_drawing` transcript fixtures replayed against Python (and C# where supported).
- **Opus Review Findings Addressed:**
  - HIGH 1: Owned drawing is guaranteed closed on unexpected exceptions (`try ... except Exception: self._close_drawing(); raise` in `check_drawing.py`).
  - HIGH 2: `StoreSet` notifies engine on first open so stores not in `known-stores.json` are recovered; store clean-up runs at engine start.
  - HIGH 3: `call_tool` maps `OSError` to `STORE_UNAVAILABLE` (`after_fix`, not `safe`), and unknown tool names raise `UnknownTool` for transport protocol-error handling (12.4.2).
  - MEDIUM/LOW: Store junctions escaping root rejected; non-finite snapshot values rejected before saving; corrupt store files handled safely; illegal transitions after final states rejected; NTFS stream names and `$` handling validated.
  - Mutation testing: all 3 surviving mutants (cursor validity, registry listed-error enforcement, document events from other jobs) covered by unit tests.
- **Not built:** Named-pipe transport, session discovery (8.6.1), heartbeat and `IpcClient` reader thread, add-in pipe host and snapshot adapter (all Milestone 6).

## Changes Made

- **Plans:** Milestone 5 implemented per [check drawing job plan](docs/superpowers/plans/2026-11-04-check-drawing-job.md).
- **Spec decisions:**
  - Settled gaps J12–J20 in `docs/specifications/open-decisions.md`; logged J21 as open.
  - Added `STORE_UNAVAILABLE` to catalogue (40 codes).
  - Clarified ADR-053 regarding engine lock boundaries during small job-record writes.
  - Topic specs at v1.23; changelog updated.

## Next Steps

1. **Implement Drawing Template IR:**
   - Execute [Drawing Template IR Implementation Plan](docs/superpowers/plans/2026-11-04-drawing-template-ir.md) per [design spec](docs/superpowers/specs/2026-11-04-drawing-template-ir-design.md).
   - Task 1: Spec update to v1.24, ADR-055 (generated sheet formats), open item K7.
   - Task 2: Module key `drawing_template` and bundle manifest validation rules.
   - Task 3: JSON schema `schemas/drawing-template/v0.json` and fixtures.
   - Task 4: Pure validator in `cad_ir.drawing_template`.
   - Task 5: Full verification and handoff.
2. **Milestone 6 ("transport and first live smoke"):**
   - Named-pipe transport and session discovery (§8.6.1).
   - Heartbeat and reader thread in `IpcClient`.
   - Core pipe and stdio front-end.
   - Add-in pipe host and live snapshot adapter.
   - First live smoke test on this PC (licensed SOLIDWORKS 2025).
3. **Owner approvals for Milestone 6:**
   - Lift "no SOLIDWORKS, no live tests" restriction.
   - Registering the add-in per user (`HKCU`) into SOLIDWORKS (ADR-038).
   - Approval of test drawing copies (ADR-022, ADR-047).
   - Engineer settings guard preferences (8.6.4, ADR-050).
   - Inspection of sheet formats in `standards/iso/templates/` to resolve K3.

## Known Issues

- **K3 remains open:** Reading title-block fields back from the owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot cannot yet report whether a draft-quality view was switched to high quality; deferred until live adapter is built.
- **J21 remains open:** C# `ScriptedHandler` cannot script JSON-RPC error responses, so `check_drawing_bad_sheet.jsonl` runs only on Python for now.
- **Unverified on real CAD:** All drawing checks and jobs have run only on synthetic snapshots and replayed IPC transcripts; live verification begins in Milestone 6.
