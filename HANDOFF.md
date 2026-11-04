# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Milestone 6 ("transport and live smoke") implementation complete. IPC named-pipe transport, session discovery, add-in pipe host, UI dispatcher, settings guard, document event monitor, drawing snapshot adapter, core pipe host, MCP front-end stdio server, and live smoke test suite are all in place.
- **Spec:** v1.23, with open items in the [register](docs/specifications/open-decisions.md): K3 (sheet format field mapping) and J11 (draft-view switched indicator in snapshot). J21 is settled. Catalogue has 40 codes.
- **Branches:** milestones 1, 2, 3, 4, 5, and 6 are merged to `main` ([#1](https://github.com/evan1ee/sw-mcp/pull/1), [#2](https://github.com/evan1ee/sw-mcp/pull/2), [#4](https://github.com/evan1ee/sw-mcp/pull/4), [#5](https://github.com/evan1ee/sw-mcp/pull/5), [#6](https://github.com/evan1ee/sw-mcp/pull/6), [#7](https://github.com/evan1ee/sw-mcp/pull/7)).
- **Verification on main:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift).
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly across all 345 files.
  - `uv run pyright` passes (0 errors, 0 warnings).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest` passes (2371 passed, 3 skipped in 39.8s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (140 passed, 0 failed).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings, 0 errors.
- **Built in Milestone 6:**
  - `apps/execution-server/ExecutionServer.Tests/Support/ScriptedHandler.cs`: C# error scripting support (J21 settled), enabling full transcript coverage on C#.
  - `packages/cad-protocol`: `NamedPipeTransport` (Windows named pipes, 4-byte little-endian framing), concurrent `IpcClient` reader thread, background heartbeat ping (`session.ping`), and safe stop/close.
  - `apps/core-service`: `discover_sessions` and `resolve_session` scanning `%LOCALAPPDATA%\sw-mcp\sessions\*.json`, cleaning dead PIDs, and `NamedPipeBackendProvider` connecting to discovered add-in sessions.
  - `apps/execution-server/ExecutionServer.AddIn`:
    - `NamedPipeServer`: current-user DACL pipe server (`\\.\pipe\sw-mcp-<pid>`) with framing.
    - `UIThreadDispatcher`: single-command UI dispatching (`ISwAddin` STA thread) with 30-second UI-blocked watchdog timer.
    - `SwAddin`: COM registration, `ISwAddin` lifecycle (`ConnectToSW`, `DisconnectFromSW`), session file publication to `%LOCALAPPDATA%\sw-mcp\sessions\<pid>.json`.
    - `SettingsGuard`: engineering settings snapshot, restoration, and crash recovery file at `%LOCALAPPDATA%\sw-mcp\settings-restore-<pid>.json`.
    - `DocumentEventMonitor`: subscriptions to `DSldWorksEvents` forwarding notifications tagged with `_meta.job_id`.
  - `apps/execution-server/ExecutionServer.Adapters`: `DrawingSnapshotAdapter`, `ViewExtractor`, `AnnotationExtractor` extracting views, polylines, dimensions, datums, and notes conforming strictly to `schemas/drawing-geometry-snapshot/v0.json` with explicit Guideline G1 COM release.
  - `apps/core-service/src/core_service/server/pipe_host.py`: Core named pipe listener (`\\.\pipe\sw-mcp-core-<id>`) with user-only ACL, exposing tools to the front-end.
  - `apps/mcp-server`: Lightweight MCP stdio front-end server (`McpServer`, `CorePipeClient`) with zero forbidden imports from core packages (enforcing Guideline G2 and import-linter contract 4).
  - `tests/live/test_live_smoke.py`: Live smoke integration suite for discovery, handshake, drawing open, snapshot extraction, and document close.
- **Live SOLIDWORKS State & Owner Gates:**
  - SOLIDWORKS 2025 SP0.1 is installed and running locally (`SLDWORKS.exe`, PID 21208).
  - Add-in has not been registered in `HKCU\Software\SolidWorks\Addins\{GUID}` because owner gate approval is required before writing to user registry and loading add-in into the interactive session. Live smoke test skips cleanly with clear reason until owner gate is executed.

## Changes Made

- **Plans:** Milestone 6 implemented per [transport and live smoke plan](docs/superpowers/plans/2026-11-04-milestone-6-transport-live-smoke.md).
- **Files Modified/Created:**
  - Python: `packages/cad-protocol/src/cad_protocol/client/pipe_transport.py`, `packages/cad-protocol/src/cad_protocol/client/ipc_client.py`, `apps/core-service/src/core_service/discovery.py`, `apps/core-service/src/core_service/server/pipe_host.py`, `apps/mcp-server/src/mcp_server/client.py`, `apps/mcp-server/src/mcp_server/server/app.py`, `apps/mcp-server/src/mcp_server/server/__init__.py`, `apps/mcp-server/src/mcp_server/py.typed`, `tests/live/test_live_smoke.py`.
  - C#: `IpcSession.cs`, `IpcSession.Commands.cs`, `NamedPipeServer.cs`, `UIThreadDispatcher.cs`, `SwAddin.cs`, `SettingsGuard.cs`, `DocumentEventMonitor.cs`, `DrawingSnapshotAdapter.cs`, `ViewExtractor.cs`, `AnnotationExtractor.cs`, `ScriptedHandler.cs`, `NamedPipeServerTests.cs`, `SettingsGuardTests.cs`, `SnapshotSchemaSerializationTests.cs`.
  - Specs & Config: `docs/specifications/open-decisions.md` (J21 marked closed), `pyproject.toml` (added `live` marker), `tests/fixtures/ipc/check_drawing_bad_sheet.jsonl`.

## Next Steps

1. **Owner Approval Gate for Live Execution:**
   - Review and execute HKCU add-in registration for `sw-mcp.AddIn.dll` (`HKCU\Software\SolidWorks\Addins\{4A137B34-3A9B-4A73-BE94-0E37C0F4A0A1}`).
   - Launch or restart SOLIDWORKS 2025 to verify add-in startup and session file creation in `%LOCALAPPDATA%\sw-mcp\sessions\`.
   - Run `uv run pytest tests/live/test_live_smoke.py` against the active session with `SW_MCP_TEST_DRAWING` pointing to a scratch copy.
2. **Milestone 7: Drawing Template IR & Production Drawing Creation:**
   - Implement Drawing Template IR according to [Drawing Template IR Implementation Plan](docs/superpowers/plans/2026-11-04-drawing-template-ir.md).
   - Address open items K3 (title block locators) and J11 (draft-view switched indicator).

## Known Issues

- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
- **Live interactive execution gated:** Live smoke tests are designed and ready, currently skipped pending owner HKCU registration gate.
