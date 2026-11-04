# Handoff

Last updated: 2026-11-04. Rules for this file: [AGENTS.md section 5](AGENTS.md#5-session-handoff).

## Current State

- **Phase:** Live Execution Gate complete & verified live against SOLIDWORKS 2025. Milestone 7 ("Drawing Template IR & Production Drawing Creation" - IR definition, schema, fixtures, contracts, pure validator & parser) complete.
- **Spec:** v1.24 across all 27 topic files. Section 11.12 authored. ADR-055 authored and recorded. Open decision register: K7 added (backend `.slddrt` generation path, blocks `later`), K3 (sheet format field mapping locators) and J11 (draft-view switched indicator) remain open. Open count is 3. Catalogue has 40 codes.
- **Branches:** PR [#8](https://github.com/evan1ee/sw-mcp/pull/8) opened from `feat/drawing-template-ir` targeting `main` (milestones 1–6 merged: [#1](https://github.com/evan1ee/sw-mcp/pull/1), [#2](https://github.com/evan1ee/sw-mcp/pull/2), [#4](https://github.com/evan1ee/sw-mcp/pull/4), [#5](https://github.com/evan1ee/sw-mcp/pull/5), [#6](https://github.com/evan1ee/sw-mcp/pull/6), [#7](https://github.com/evan1ee/sw-mcp/pull/7)).
- **Verification on main & live:**
  - `uv run python scripts/generate_contracts.py --check` passes cleanly (0 drift).
  - `uv run ruff check` and `uv run ruff format --check` pass cleanly across all 352 files.
  - `uv run pyright` passes (0 errors, 0 warnings).
  - `uv run lint-imports` passes (5 contracts kept, 0 broken).
  - `uv run pytest` passes (2,427 passed, 1 skipped in 38.6s).
  - `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes (140 passed, 0 failed).
  - `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings, 0 errors.
- **Live SOLIDWORKS State & Execution Gate:**
  - SOLIDWORKS 2025 SP0.1 active interactive desktop session running (`SLDWORKS.exe`, PID 38972).
  - Owner approval gate granted and executed. Add-in registered in `HKLM` and `HKCU` via `scripts/register_addin_admin.reg` and `scripts/register_addin_admin.ps1`.
  - Added in-process `AssemblyResolve` handler to `SwAddin.cs` to resolve `ExecutionServer.Core.dll` and `Newtonsoft.Json.dll` from the add-in binary folder inside SOLIDWORKS.
  - `sw-mcp Add-In` is actively loaded in SOLIDWORKS 2025 (load time `< 1s`), published `%LOCALAPPDATA%\sw-mcp\sessions\38972.json`, and listening on named pipe `\\.\pipe\sw-mcp-addin-38972-47336a35`.
  - Live smoke test results (`tests/live/test_live_smoke.py`):
    - `test_live_session_discovery`: PASSED
    - `test_live_session_handshake`: PASSED (JSON-RPC `session.hello` verified)
    - `test_live_drawing_snapshot`: PASSED (verified live against `dissectiontemplate.slddrw`, schema validation passed cleanly)

## Changes Made

- **Live Execution Gate:**
  - Added in-process assembly resolution hook (`AppDomain.CurrentDomain.AssemblyResolve`) in `apps/execution-server/ExecutionServer.AddIn/SwAddin.cs` to support .NET COM loading in `SLDWORKS.exe`.
  - Added connection diagnostic logging to `%LOCALAPPDATA%\sw-mcp\addin-load.log`.
  - Added admin registration scripts: `scripts/register_addin_admin.reg`, `scripts/register_addin_admin.ps1`, `scripts/unregister_addin_admin.reg`.
  - Verified live pipe discovery and handshake in real SOLIDWORKS 2025 session.

## Next Steps

1. **Live Snapshot Verification with Scratch Drawing:**
   - Place a scratch `.slddrw` copy in temporary storage and run `test_live_drawing_snapshot` via `SW_MCP_TEST_DRAWING=<path> uv run pytest tests/live/test_live_smoke.py`.
2. **Backend `.slddrt` Generation (K7):**
   - Resolve open decision K7 in `docs/specifications/open-decisions.md` and implement `sheet_format.generate` in `ExecutionServer.AddIn` using SOLIDWORKS DrawingDoc sheet format API.
3. **Production Drawing Creation Pipeline:**
   - Implement drawing compilation, sheet format injection/binding, view creation, and annotation placement.

## Known Issues

- **K7 open:** Backend generation path for `.slddrt` in SOLIDWORKS is logged in `docs/specifications/open-decisions.md` and deferred until live drawing generation is tackled.
- **K3 remains open:** Reading title-block fields back from owner's templates requires inspecting `standards/iso/templates/` in SOLIDWORKS to define locators in §13.3.4.
- **J11 remains open:** Snapshot does not yet report whether a draft-quality view was switched to high quality; awaiting interactive inspection.
