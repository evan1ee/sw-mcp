# Milestone 6: Named-Pipe Transport, Add-In Host and First Live Smoke Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Windows named-pipe transport and session discovery (§8.6.1), the concurrent reader thread and heartbeat in `IpcClient` (§8.6.2, ADR-053), the C# in-process add-in pipe host and UI-thread dispatcher (`ExecutionServer.AddIn`), the engineer settings guard (§8.6.4), the C# live drawing snapshot adapter (`ExecutionServer.Adapters`), the core-service front-end pipe and stdio MCP server (`apps/mcp-server`, ADR-041), and conduct the first live smoke test against local SOLIDWORKS 2025.

**Architecture:**
- **Protocol & Transport (`cad-protocol`):** Length-prefixed binary framing over Windows named pipes (`\\.\pipe\...`). Background reader thread handles incoming frames, dispatches results to waiters, routes notifications to callbacks, and reassembles chunks. Heartbeat background thread sends `session.ping` when idle. Thread-safe cancellation unblocks long-running calls.
- **Session Discovery (`core-service`):** Scans `%LOCALAPPDATA%\sw-mcp\sessions\*.json` for live SOLIDWORKS processes (`is_process_running(pid)`), purges stale session records, and resolves `"auto"` or explicit PID per §8.6.1 (`NamedPipeBackendProvider`).
- **C# In-Process Add-In Host (`ExecutionServer.AddIn`):** `ISwAddin` lifecycle hooks `ConnectToSW` and `DisconnectFromSW`. Captures `SynchronizationContext` on the main UI thread. Creates pipe `\\.\pipe\sw-mcp-addin-<pid>-<random>` with current-user DACL and writes session file. Posts commands to UI thread while handling `session.ping` and `job.cancel` concurrently on the pipe thread. Enforces 30 s UI-blocked timer (§8.6.3).
- **Settings Guard & Event Tagging (`ExecutionServer.AddIn`):** `SettingsGuard` snapshots touched user preferences to `%LOCALAPPDATA%\sw-mcp\settings-restore-<pid>.json` and restores them on job completion or crash recovery (§8.6.4). Subscribes to document events and tags job-originating events with `_meta.job_id` (§8.4, §8.6.5).
- **Live Snapshot Adapter (`ExecutionServer.Adapters`):** Real SOLIDWORKS API calls reading drawing sheets, views, annotations, and dimensions into the Drawing Geometry Snapshot schema. Adheres strictly to Guideline G1 (explicit `Marshal.ReleaseComObject` in `finally` blocks).
- **Core Pipe & MCP Stdio Server (`apps/mcp-server`):** Stateless stdio MCP front-end forwarding tool calls across `\\.\pipe\sw-mcp-core-<sid>` to `core-service` (ADR-041).

**Tech Stack:**
- Python 3.13: `_winapi`, `ctypes`, `threading`, standard library.
- C# .NET Framework 4.8: SOLIDWORKS 2025 Interop assemblies, `System.IO.Pipes`, `System.Threading`, Newtonsoft.Json.

**Spec & Decisions:**
- §8.6 (Add-in runtime: loading, discovery, threading, timeouts, settings guard, document events).
- §8.7 (IPC messages: handshake, error codes, dispatch, chunks, cancellation).
- §8.4 & §11.5.1 (Snapshot schema and job lifecycle).
- ADR-028 (In-process add-in), ADR-036 (IPC protocol), ADR-038 (Per-user registration), ADR-041 (Core service & front-end topology), ADR-045 (Version compatibility), ADR-050 (Shared session guard), ADR-053 (Job engine & reader thread concurrency).

---

## Owner Approvals & Environmental Gates

Executing live tests against real SOLIDWORKS requires explicit owner authorization per ADR-022, ADR-038, ADR-047, and ADR-050:

1. **Gate 1 (Tasks 1–4): Synthetic & Transport Tests (No SOLIDWORKS required)**
   - All tests run against mock/simulated pipes and scripted transcripts. No SOLIDWORKS process started or touched.
2. **Gate 2 (Before Task 5 & 8): Add-In Registration Approval**
   - Requires writing add-in registration keys into `HKCU\Software\SolidWorks\Addins\{GUID}` and loading inside SOLIDWORKS.
3. **Gate 3 (Before Task 8): Live Session & Drawing Custody Approval**
   - Approval to connect to local SOLIDWORKS 2025 interactive session.
   - Approval of test drawing copies placed in temporary scratch folder (source files and vaulted files remain read-only/untouched per ADR-022).

---

## Global Constraints

- **Purity & Dependencies (Guideline G2):** Pure core packages remain zero-I/O. `cad-application` never imports `cad-protocol` or platform APIs. `core-service` and `apps/mcp-server` host the transport.
- **COM Object Safety (Guideline G1):** Every COM object in `ExecutionServer.AddIn` and `ExecutionServer.Adapters` must be explicitly released using `Marshal.ReleaseComObject` in `finally` blocks. Never use `Marshal.FinalReleaseComObject`. No COM objects leave the STA UI thread.
- **Banned APIs:** Banned SOLIDWORKS symbols in `BannedSymbols.txt` are enforced at build time.
- **Determinism:** Tests must not use arbitrary wall-clock sleeps. Cross-thread tests use `threading.Event` synchronization with bounded safety timeouts.
- **Zero Completion Claims Without Fresh Verification:** All suites (`ruff`, `pyright`, `lint-imports`, `pytest`, `dotnet test`, `dotnet build`) must pass cleanly with evidence before completion.

---

## Task Breakdown

### Task 1: Transcript Harness Error Scripting (J21 Settlement)

**Goal:** Enable `ScriptedHandler` in C# test harness to script JSON-RPC error responses from IPC transcripts, resolving open decision J21 and allowing `check_drawing_bad_sheet.jsonl` to run on both Python and C#.

**Files:**
- Modify: `apps/execution-server/ExecutionServer.Tests/Support/ScriptedHandler.cs`
- Modify: `tests/fixtures/ipc/check_drawing_bad_sheet.jsonl` (add `"csharp"` to `sides`)
- Modify: `docs/specifications/open-decisions.md` (record J21 as closed)

- [ ] **Step 1:** Write unit test in C# for `ScriptedHandler` throwing `IpcException` when transcript frame has `error`.
- [ ] **Step 2:** Update `ScriptedHandler.cs` to inspect `r["error"]` and throw `IpcException(code, message, details)`.
- [ ] **Step 3:** Update `check_drawing_bad_sheet.jsonl` to set `sides: ["python", "csharp"]`.
- [ ] **Step 4:** Verify: `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` passes all 128 tests.

---

### Task 2: Python Named-Pipe Client Transport & Concurrent Reader Thread

**Goal:** Implement low-level Windows named pipe transport (`NamedPipeTransport`) and equip `IpcClient` with a dedicated background reader thread and heartbeat loop per §8.6.2 and ADR-053.

**Files:**
- Create: `packages/cad-protocol/src/cad_protocol/client/pipe_transport.py`
- Modify: `packages/cad-protocol/src/cad_protocol/client/ipc_client.py`
- Create: `packages/cad-protocol/tests/test_pipe_transport.py`
- Create: `packages/cad-protocol/tests/test_ipc_client_concurrency.py`

- [ ] **Step 1: Failing Tests:**
  - `test_named_pipe_send_and_receive`: connects to a local Windows named pipe server, sends framed message, receives framed reply.
  - `test_named_pipe_connect_failure`: raises `TransportClosed` when pipe does not exist.
  - `test_named_pipe_timeout`: raises `TransportTimeout` when read deadline is exceeded.
  - `test_reader_thread_dispatches_responses`: incoming responses match pending requests by ID and wake waiters via `Event`.
  - `test_reader_thread_routes_notifications`: incoming `session.ui_blocked` and `document.event` route to `on_notification` without blocking request callers.
  - `test_concurrent_cancellation`: `client.cancel()` sends `job.cancel` concurrently from a secondary thread while a command request is waiting.
  - `test_heartbeat_sends_ping_when_idle`: periodic `session.ping` sent when channel is idle; 3 missed pongs closes connection with `BACKEND_LOST`.
- [ ] **Step 2:** Implement `NamedPipeTransport` using Win32 API (`CreateFileW`, `ReadFile`, `WriteFile`, `PeekNamedPipe`, `CloseHandle`).
- [ ] **Step 3:** Update `IpcClient` with thread-safe `_pending` map protected by `_lock`, background `_reader_thread` loop, and idle `_heartbeat_loop`.
- [ ] **Step 4:** Verify: `uv run pytest packages/cad-protocol` passes cleanly.

---

### Task 3: Session Discovery & Backend Provider

**Goal:** Implement session discovery scanning `%LOCALAPPDATA%\sw-mcp\sessions\*.json` with process liveness checks and `NamedPipeBackendProvider` in `core-service`.

**Files:**
- Create: `apps/core-service/src/core_service/discovery.py`
- Modify: `apps/core-service/src/core_service/providers.py`
- Create: `apps/core-service/tests/test_session_discovery.py`
- Modify: `apps/core-service/tests/test_providers.py`

- [ ] **Step 1: Failing Tests:**
  - `test_discovery_finds_live_session`: valid session file of running PID parsed into `SessionInfo`.
  - `test_discovery_purges_stale_sessions`: session files for non-existent PIDs or invalid JSON are deleted.
  - `test_resolve_session_auto_single`: selects the single active session.
  - `test_resolve_session_auto_none`: raises `BackendUnavailable("BACKEND_LOST", ...)`.
  - `test_resolve_session_auto_multiple`: raises `BackendUnavailable("BACKEND_SESSION_AMBIGUOUS", ...)` with `pids` in details.
  - `test_resolve_session_explicit_pid`: matches requested PID or raises `BACKEND_LOST`.
  - `test_named_pipe_backend_provider_acquire`: acquires discovered session, performs `session.hello` handshake, and handles version mismatch (`BACKEND_VERSION_UNSUPPORTED`).
- [ ] **Step 2:** Implement `scan_sessions`, `is_process_running`, `resolve_session`, and `NamedPipeBackendProvider`.
- [ ] **Step 3:** Verify: `uv run pytest apps/core-service` passes cleanly.

---

### Task 4: C# Add-In Pipe Host & UI Thread Dispatcher

**Goal:** Build the named-pipe server and UI-thread command dispatcher inside `ExecutionServer.AddIn` per §8.6.1 and §8.6.2.

**Files:**
- Create: `apps/execution-server/ExecutionServer.AddIn/Pipe/NamedPipeServer.cs`
- Create: `apps/execution-server/ExecutionServer.AddIn/Dispatch/UIThreadDispatcher.cs`
- Create: `apps/execution-server/ExecutionServer.AddIn/SwAddin.cs`
- Modify: `apps/execution-server/ExecutionServer.AddIn/ExecutionServer.AddIn.csproj`
- Create: `apps/execution-server/ExecutionServer.Tests/Pipe/NamedPipeServerTests.cs`

- [ ] **Step 1: Failing Tests in ExecutionServer.Tests:**
  - `PipeServer_RejectsFirstFrameIfNotHello`: closing pipe without response when first request is not `session.hello` or invalid token.
  - `PipeServer_HandlesPingOnPipeThread`: `session.ping` answered immediately on pipe thread without queuing to UI thread.
  - `PipeServer_DispatchesCommandsToSynchronizationContext`: commands posted to `SynchronizationContext` and executed sequentially.
  - `PipeServer_EnforcesUiBlockedTimeout`: when command posted to UI thread does not begin executing within 30 s, emits `session.ui_blocked` notification.
- [ ] **Step 2:** Implement `NamedPipeServer` using `NamedPipeServerStream`, `PipeSecurity` restricted to current user, and framing matching `cad-protocol`.
- [ ] **Step 3:** Implement `UIThreadDispatcher` wrapping captured `SynchronizationContext` with single-command queueing and timeout monitoring.
- [ ] **Step 4:** Implement `SwAddin` (`ISwAddin`) implementing `ConnectToSW` and `DisconnectFromSW` lifecycle: token generation, session file write/delete, and pipe server startup/shutdown.
- [ ] **Step 5:** Verify: `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj` and `dotnet build apps/execution-server/ExecutionServer.sln`.

---

### Task 5: C# Engineer Settings Guard & Document Event Tagging

**Goal:** Implement preference isolation guard (`SettingsGuard`) and document event notification tagging in `ExecutionServer.AddIn` per §8.6.4 and §8.6.5.

**Files:**
- Create: `apps/execution-server/ExecutionServer.AddIn/Diagnostics/SettingsGuard.cs`
- Create: `apps/execution-server/ExecutionServer.AddIn/Events/DocumentEventMonitor.cs`
- Create: `apps/execution-server/ExecutionServer.Tests/Diagnostics/SettingsGuardTests.cs`

- [ ] **Step 1: Failing Tests:**
  - `SettingsGuard_SnapshotsAndRestoresPreferences`: records original settings, allows overrides during job, restores exactly on completion.
  - `SettingsGuard_RecoversFromCrashFile`: recovers and restores settings from `%LOCALAPPDATA%\sw-mcp\settings-restore-<pid>.json` left by a previous crashed session.
  - `DocumentEventMonitor_TagsJobEvents`: verifies that events raised during an active command carry `_meta.job_id`, while user interactions carry no `job_id`.
- [ ] **Step 2:** Implement `SettingsGuard` handling user preference toggles and integer values, recording state to disk, and restoring in `finally` / startup.
- [ ] **Step 3:** Implement `DocumentEventMonitor` subscribing to SOLIDWORKS `DSldWorksEvents` and `DDrawingDocEvents`, forwarding events as JSON-RPC notifications.
- [ ] **Step 4:** Verify: `dotnet test` passes.

---

### Task 6: C# Live Drawing Snapshot Adapter

**Goal:** Implement real SOLIDWORKS API extraction of drawing geometry, views, dimensions, and annotations into the Drawing Geometry Snapshot schema in `ExecutionServer.Adapters`.

**Files:**
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/DrawingSnapshotAdapter.cs`
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/ViewExtractor.cs`
- Create: `apps/execution-server/ExecutionServer.Adapters/Drawings/AnnotationExtractor.cs`
- Modify: `apps/execution-server/ExecutionServer.Adapters/ExecutionServer.Adapters.csproj`
- Create: `apps/execution-server/ExecutionServer.Tests/Drawings/SnapshotSchemaSerializationTests.cs`

- [ ] **Step 1: Failing Tests:**
  - Serialization tests in `ExecutionServer.Tests` ensuring C# adapter DTOs produce JSON strictly compliant with `schemas/drawing/snapshot/v0.json`.
  - Sheet filtering tests verifying `sheets` param filters sheets and non-existent sheets return `IR_REFERENCE_UNRESOLVED`.
- [ ] **Step 2:** Implement `ViewExtractor` traversing `IView` on drawing sheets, reading scale, projection, bounding box, quality (draft vs high), and polylines.
- [ ] **Step 3:** Implement `AnnotationExtractor` extracting display dimensions, tolerances, dual units, witness lines, text notes, surface finishes, and datum features. Enforce Guideline G1 (`Marshal.ReleaseComObject` on all COM objects).
- [ ] **Step 4:** Connect adapter to `drawing.snapshot` command handler in dispatcher.
- [ ] **Step 5:** Verify: `dotnet test` passes and `dotnet build apps/execution-server/ExecutionServer.sln` succeeds with 0 warnings/errors.

---

### Task 7: Core Named-Pipe Front-End Listener & MCP Stdio Server

**Goal:** Implement the long-lived core service pipe listener (`\\.\pipe\sw-mcp-core-<sid>`) and the lightweight stdio MCP server front-end in `apps/mcp-server` per ADR-041.

**Files:**
- Create: `apps/core-service/src/core_service/server/pipe_host.py`
- Modify: `apps/core-service/src/core_service/service.py`
- Create: `apps/mcp-server/src/mcp_server/client.py`
- Create: `apps/mcp-server/src/mcp_server/server.py`
- Create: `apps/mcp-server/tests/test_mcp_front_end.py`

- [ ] **Step 1: Failing Tests:**
  - `test_core_pipe_host_receives_tool_call`: connects over core named pipe, sends `tools/call`, receives `ToolResult`.
  - `test_mcp_front_end_lists_tools`: MCP stdio server responds to `tools/list` with schema contracts from core.
  - `test_mcp_front_end_forwards_tool_call`: MCP stdio server calls `check_drawing` via core pipe and returns JSON response.
- [ ] **Step 2:** Implement `PipeHost` in `core_service` listening on `\\.\pipe\sw-mcp-core-<sid>` with user-only ACL.
- [ ] **Step 3:** Implement stdio MCP server in `apps/mcp-server` forwarding MCP protocol messages to the core service pipe.
- [ ] **Step 4:** Verify: `uv run pytest apps/mcp-server` and `uv run lint-imports` pass.

---

### Task 8: Live Smoke Verification on SOLIDWORKS 2025

**Goal:** Perform live end-to-end verification against the local licensed SOLIDWORKS 2025 installation under owner approval gates.

**Files:**
- Create: `tests/live/test_live_smoke.py`
- Modify: `HANDOFF.md`

- [ ] **Step 1 (Owner Gate Check):** Confirm owner approval for `HKCU` add-in registration and scratch drawing copy execution.
- [ ] **Step 2:** Register `sw-mcp.AddIn.dll` in `HKCU\Software\SolidWorks\Addins\{GUID}`.
- [ ] **Step 3:** Launch or connect to local SOLIDWORKS 2025 interactive session and verify session file created in `%LOCALAPPDATA%\sw-mcp\sessions\`.
- [ ] **Step 4:** Run live smoke test `test_live_smoke.py`:
  - Discover session file and establish named-pipe handshake (`session.hello`).
  - Open scratch test drawing (`ops.apply` with `document.open`).
  - Execute `drawing.snapshot` and validate output against JSON Schema.
  - Execute `check_drawing` job via `CoreService` and verify report generation in project store.
  - Verify `SettingsGuard` restored all SOLIDWORKS settings.
  - Close test drawing (`document.close`).
- [ ] **Step 5:** Run full project verification suite across Python and C#.
- [ ] **Step 6:** Update `HANDOFF.md` to record Milestone 6 completion, live test results, and next steps for Milestone 7.
