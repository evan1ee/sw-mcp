# IPC Contract, Python Client and C# Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the add-in protocol in `schemas/ipc/`, generate Python and C# types from it, and implement the Python client (with `ReplayBackend`) and C# `ExecutionServer.Core`, each tested against the same transcripts with no SOLIDWORKS.

**Architecture:** `schemas/ipc/v0.json` is the contract. `scripts/generate_contracts.py` emits `cad_ir/generated/ipc.py` and `ExecutionServer.Core/Ipc/Generated/*.g.cs`. Hand-written transcripts in `tests/fixtures/ipc/` are replayed against each side separately (15.5). `Core` has no threads of its own: the pipe thread calls `IpcSession.Receive`, the UI thread calls `IpcSession.RunNext`, so all of it runs in a test.

**Tech Stack:** Python 3.13 (no new dependencies); C# on net48 with `Newtonsoft.Json` 13.x (ADR-052), xUnit.

**Spec:** `docs/architecture/execution-engine.md` §8.7 (read it first: it fixes every protocol rule below), §8.2, §8.3 rule 8; `docs/architecture/addin-runtime.md` §8.6.1–8.6.3; `docs/architecture/backend-operations.md` §6.5.1, §6.6; `docs/development/testing-strategy.md` §15.5; ADR-036, ADR-037, ADR-038, ADR-045, ADR-051, ADR-052; guidelines G1, G2.

## Global Constraints

- The Global Constraints of `2026-11-03-shared-ir-core.md` apply: pyright strict, ruff, §3.4.8 schema rules, generated files only via `scripts/generate_contracts.py`.
- `.gitattributes` makes `*.cs` CRLF and everything else LF. Generated `.g.cs` text must use `\r\n`, or `--check` fails on a fresh checkout.
- Layering: `cad_application` must not import `cad_protocol`, and `cad_protocol` must not import `cad_application` (G2). `ExecutionServer.Core` has no SOLIDWORKS reference (ADR-038).
- Never log or put in an exception message: session tokens (G3).
- No SOLIDWORKS, no live tests, no real named pipe, and nothing from the reference implementation.
- **Do not run git add or commit.** The controller commits after review.
- Python suite after every task, from the repo root: `uv run python scripts/generate_contracts.py --check && uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest -q`.
- C# suite: `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.

## Review Focus

1. **Unauthenticated clients learn nothing.** A wrong token, or a first frame that is not `session.hello`, closes with no reply; no exception or log text holds the token. Tests: `wrong_token` and `not_hello_first` transcripts, `Token_never_appears_in_exception_or_ToString`.
2. **A timeout is never resent.** After `EXEC_TIMEOUT` the client sends nothing for that call, and a late response or late chunks are discarded without confusing the next call. Tests: `timeout_late_response` transcript, `test_late_chunks_are_discarded`.
3. **Chunks split bytes, not text.** A multi-byte character straddling a chunk boundary survives, every frame stays within the limit, and notifications between chunks are delivered. Tests: `test_chunks_split_inside_a_character`, `Chunked_response_frames_stay_within_limit`, `snapshot_chunked` transcript.
4. **Cancel ordering.** Queued commands answer `EXEC_CANCELLED` first, and the cancel response waits for the running command. Tests: `cancel_running` transcript, `Cancel_when_idle_answers_false`.
5. **A closed pipe doesn't lose work.** A command running when the pipe closes finishes, records its operations in the ledger and doesn't throw; a new session on the same ledger sees them. Test: `Command_running_at_close_records_in_ledger`.

---

### Task 1: Schemas, fixtures and generators

**Files:**
- Create: `schemas/ipc/v0.json` (delete `schemas/ipc/.gitkeep`), `schemas/ipc/ops/document.open.json`, `schemas/ipc/ops/document.close.json`; `tests/fixtures/schemas/ipc/{valid,invalid}/*.json`
- Modify: `scripts/generate_contracts.py`, plus a new module `scripts/contract_types.py` if the script would pass 400 lines; `tests/contract/test_schema_fixtures.py`, `tests/contract/test_generated_contracts.py`
- Generated: `packages/cad-ir/src/cad_ir/generated/ipc.py`; `apps/execution-server/ExecutionServer.Core/Ipc/Generated/Messages.g.cs`, `ErrorCodes.g.cs`
- Delete: the empty scaffold `packages/cad-protocol/src/cad_protocol/generated/`
- Modify: `ExecutionServer.Core.csproj`: add `Newtonsoft.Json` 13.0.3

**`schemas/ipc/v0.json` `$defs`** (root: `anyOf` of `Request`, `Response`, `Notification`). Objects are open (lenient readers, ADR-042). `_meta` is optional on every params object.
- Envelope: `Meta {request_id?, job_id?, operation_id?}`; `Request {jsonrpc: const "2.0", id: Count, method: string, params?: object}`; `Response {jsonrpc, id: Count or null, result?, error?: RpcError}`; `RpcError {code: integer, message: string, data?: $ref common Error}`; `Notification {jsonrpc, method, params?}` (no `id`)
- Session: `HelloParams {token, protocol, _meta?}`; `SolidWorksInfo {version, service_pack, ui_language}`; `OperationInfo {op, schema_version}`; `HelloResult {protocol, addin_version, solidworks, capabilities: [string], operations: [OperationInfo], licensed_modules: [string], warnings: [string]}`, all required; `PingParams {_meta?}`; `PingResult {pong: const true}`; `CompletedOperationsParams {_meta?}`; `CompletedOperationsResult {operation_ids: [string]}`
- Commands: `SnapshotParams {document, sheets?: [string], _meta?}`; `SnapshotResult`: a `$ref` to `../drawing-geometry-snapshot/v0.json` (opaque to the generator); `Operation {operation_id, op, params?: object}`; `OperationGroup {document, operations: [Operation] (minItems 1)}`; `OpsApplyParams {groups: [OperationGroup] (minItems 1), _meta?}`; `OperationOutcome {operation_id, result?, error?: $ref common Error}`; `OpsApplyResult {outcomes: [OperationOutcome]}`; `JobCancelParams {_meta?}`; `JobCancelResult {cancelled: boolean}`
- Notifications: `JobProgressParams {message?, done?: Count, total?: Count, _meta?}`; `DocumentEventParams {document, event: enum regen|save|close|active_changed, _meta?}`; `UiBlockedParams {waited_ms: Count, _meta?}`; `ResponseChunkParams {id: Count, index: Count, count: Count, data: string}`

**`schemas/ipc/ops/<op>.json`:** annotations `x-op`, `x-mutates`, `x-errors`, `x-since` ("0.1"), and `$defs` `Params` and `Result`. `document.open`: `x-mutates: session`; Params `{path, read_only: boolean, fully_resolved: boolean, configuration?}`; Result `{owned: boolean}` (ADR-046). `document.close`: `x-mutates: session`; Params `{path}`; Result `{closed: boolean}`. Generated names: `DocumentOpenParams`, `DocumentOpenResult`, `DocumentCloseParams`, `DocumentCloseResult`.

**Generated Python (`ipc.py`):** one frozen, slots dataclass per object def; `PROTOCOL_VERSION = "0.1"`, taken from the `x-protocol-version` annotation at the schema root. Each has `from_json(cls, value: JsonValue) -> Self` (raises `ValueError` naming the field on a missing required field or wrong JSON type; ignores unknown fields) and `to_json(self) -> dict[str, JsonValue]` (omits `None`). Field `_meta` maps to attribute `meta`. Enums are `Literal` aliases, not checked at read (ADR-042). Opaque values are `JsonValue`. Lists are tuples.

**Generated C#:** namespace `ExecutionServer.Core.Ipc.Generated`; one `sealed class` per object def with `[JsonProperty("x", Required = Required.Always)]` on required members and `NullValueHandling.Ignore` on optional ones; PascalCase properties; enums as C# `enum` with `[EnumMember(Value = ...)]` and `StringEnumConverter`; opaque values are `JToken?`; lists are `List<T>`. `ErrorCodes.g.cs`: `public static class ErrorCodes` with one `const string` per catalogue code, and `DefaultRetryable(string code)`.

**Generator rule (ADR-051):** a shape outside the supported set raises `SystemExit` naming the schema path. Output order is deterministic.

**Fixtures:** as `common`: `valid/<Def>.json` and `invalid/<Def>.json` hold arrays of instances. `invalid/structural_<Def>.json` holds only instances C# deserialization must also reject (missing required field, wrong JSON type, unknown enum value). Every def has a `valid` file; every def with a required field has an `invalid` file and at least one case in `structural_*`.

- [ ] **Step 1: Failing tests:**
  - in `test_schema_fixtures.py`: `test_ipc_valid_accepted`, `test_ipc_invalid_rejected` (both prefixes), `test_every_ipc_def_has_fixtures`, `test_ops_schemas_declare_annotations`
  - in `test_generated_contracts.py`: `test_ipc_python_models_accept_valid_fixtures` (every valid fixture: `from_json` then `to_json` equals the input for closed shapes), `test_ipc_python_models_reject_structural` (`ValueError`), `test_unknown_fields_ignored`, `test_generator_rejects_unsupported_shape` (`oneOf` in a temp schema gives `SystemExit` naming the path), `test_csharp_output_uses_crlf`, `test_generated_cs_is_checked` (a stale `.g.cs` fails `--check`), `test_orphan_cs_is_reported`
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the schemas and fixtures; extend the generator; run it.
- [ ] **Step 4:** Run the Python suite. Run `dotnet build apps/execution-server/ExecutionServer.Core/ExecutionServer.Core.csproj`. Expected: both pass; warnings are errors.

### Task 2: Transcripts, framing, Python client and ReplayBackend

**Files:**
- Create: `tests/fixtures/ipc/*.jsonl`; `packages/cad-protocol/src/cad_protocol/framing.py`, `errors.py`, `client/ipc_client.py`, `client/transport.py`, `backend.py`, `replay.py`; `packages/cad-application/src/cad_application/ports.py`
- Test: `packages/cad-protocol/tests/test_framing.py`, `test_ipc_client.py`, `test_replay.py`; `tests/contract/test_transcripts.py`, `tests/contract/test_backend_port.py`

**Interfaces (Produces):**
- `framing.py`: `MAX_FRAME_BYTES = 64 * 1024 * 1024`; `encode_frame(payload: bytes, max_bytes: int = MAX_FRAME_BYTES) -> bytes`; `read_frame(stream: BinaryIO, max_bytes: int = MAX_FRAME_BYTES) -> bytes | None` (None at a clean end of stream; `FrameError` on a truncated frame or a length over the limit, checked before reading the body)
- `transport.py`: `Transport` Protocol: `send(payload: bytes) -> None`, `receive(timeout_s: float) -> bytes`, `close() -> None`. `TransportTimeout`, `TransportClosed`.
- `errors.py`: `IpcError(Exception)` with `code: str`, `message: str`, `retryable: str`, `details: JsonValue`, `original_result: JsonValue | None`; `IpcProtocolFault(Exception)` with `rpc_code: int`, `message: str`, for `-326xx`
- `ipc_client.py`: `IpcClient(transport, *, token, on_notification: Callable[[str, JsonValue], None] | None = None, read_timeout_s: float = 30.0, command_timeout_s: float = 120.0)`. Methods: `hello() -> HelloResult`, `ping() -> PingResult`, `completed_operations() -> tuple[str, ...]`, `snapshot_drawing(document, sheets=None, *, meta=None) -> JsonValue`, `apply_ops(groups, *, meta=None) -> OpsApplyResult`, `cancel(*, meta=None) -> bool`, `close() -> None`. Ids count from 1. `snapshot_drawing` and `apply_ops` use `command_timeout_s`; the others use `read_timeout_s`. A transport timeout raises `IpcError("EXEC_TIMEOUT")`; a closed transport raises `IpcError("BACKEND_LOST")`. A wrong major in `HelloResult.protocol` closes and raises `IpcError("BACKEND_VERSION_UNSUPPORTED")`.
- `ports.py`: `Backend` Protocol: `session: HelloResult` (property), `snapshot_drawing`, `apply_ops`, `completed_operations`, `cancel`, with the client's signatures, importing types only from `cad_ir.generated.ipc`. Add `cad-ir` to `cad-application`'s dependencies if absent.
- `backend.py`: `IpcBackend(client: IpcClient)`: calls `hello()` on construction; structurally a `Backend`.
- `replay.py`: `Transcript` (`header`, `entries`), `load_transcript(text: str) -> Transcript` (pure, takes text), `ReplayTransport(transcript)`, `replay_backend(transcript) -> IpcBackend`. `send` compares the frame with the next `core_to_addin` entry using the §8.7 masking and raises `TranscriptMismatch` showing both. `receive(timeout_s)` returns the next `addin_to_core` frame, raises `TransportClosed` at a `close` entry, and raises `TransportTimeout` when that frame's `t_ms` minus the last sent frame's `t_ms` exceeds the limit (no real waiting). After a timeout, the frame stays next in line.

**Transcript scenarios** (all `source: synthetic`; `sides` both unless stated):

| Scenario | Frames |
| --- | --- |
| `handshake` | hello, result; ping, pong; completed_operations, empty |
| `wrong_token` | hello with a bad token; close |
| `not_hello_first` | ping; close |
| `protocol_major_mismatch` | hello with `9.0`; `BACKEND_VERSION_UNSUPPORTED`; close |
| `solidworks_unsupported` | hello; `BACKEND_VERSION_UNSUPPORTED`; hello again; same error (pipe stays open) |
| `snapshot_ok` | hello; `drawing.snapshot`; `job.progress`; `document.event`; result, a valid snapshot |
| `snapshot_chunked` | hello; `drawing.snapshot`; chunk 0; `job.progress`; chunks 1..n; `config.max_frame_bytes` small |
| `cancel_running` | hello; snapshot id 2; snapshot id 3 (queued); `job.cancel` id 4; id 3 `EXEC_CANCELLED`; id 2 `EXEC_CANCELLED`; id 4 `{cancelled: true}` |
| `ops_duplicate` | hello; `ops.apply` with `document.open`, `document.close`, ids `j1:1`, `j1:2`; two outcomes; same call with `j1:2` then `j1:3`: one outcome, `DUPLICATE_OPERATION` with `result`; completed_operations gives `j1:1`, `j1:2` |
| `ops_failure_stops` | a batch of 3, the second fails; two outcomes; completed_operations gives only the first |
| `ui_blocked` | hello; snapshot; `session.ui_blocked`; result. The notification is only delivered: failing the job is the core's decision (8.6.3), not the client's (sides: python) |
| `timeout_late_response` | hello; snapshot, with the add-in's result later than the limit; completed_operations; the late result, then its answer (sides: python) |
| `backend_lost` | hello; snapshot; close (sides: python) |
| `unknown_method` | hello; `nope.nope`; `-32601` (sides: csharp) |
| `invalid_params` | hello; `drawing.snapshot` with no `document`; `-32602` (sides: csharp) |

- [ ] **Step 1: Failing tests:**
  - `test_framing.py`: `test_golden_bytes` (payload `{"id":1}` is `08 00 00 00` then the payload), `test_round_trip`, `test_truncated_header_and_body`, `test_length_over_limit_rejected_before_reading`, `test_clean_end_returns_none`
  - `test_replay.py`: `test_mismatched_send_raises`, `test_masks_meta`, `test_timeout_from_t_ms`
  - `test_ipc_client.py`, each over a transcript:
    - `test_handshake`, `test_wrong_token_is_backend_lost`, `test_token_not_in_error_text`, `test_major_mismatch_error`, `test_returned_major_mismatch_closes` (built in code), `test_snapshot_delivers_notifications_in_order`
    - `test_chunks_joined`, `test_chunks_split_inside_a_character` (built in code: a boundary inside `草`), `test_late_chunks_are_discarded` (built in code), `test_chunk_out_of_order_or_bad_count_is_protocol_fault` (built in code)
    - `test_cancel_running`, `test_duplicate_carries_original_result` (`outcomes[0].error.code` and `.result`), `test_failure_stops_batch`
    - `test_timeout_no_resend_then_late_response_discarded` (`TranscriptMismatch` would fire on any resend), `test_backend_lost`, `test_unknown_error_code_kept_as_text` (built in code), `test_protocol_fault_raised` (built in code), `test_ui_blocked_notification_delivered`
  - `tests/contract/test_transcripts.py`: `test_every_transcript_header_valid`, `test_every_frame_matches_ipc_schema` (each frame against the root; params and results against the def for its method, via a table in the test; `drawing.snapshot` results against the snapshot schema), `test_every_python_scenario_replays_to_the_end` (a table maps scenario to driver; every `python` scenario has one, and all frames are consumed), `test_all_scenarios_present`
  - `tests/contract/test_backend_port.py`: `test_ipc_backend_is_a_backend`: `backend: Backend = replay_backend(...)`, so pyright checks conformance, plus one call
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the transcripts, then implement.
- [ ] **Step 4:** Run the Python suite plus `uv run pytest --cov=packages/cad-protocol/src --cov-report=term -q packages/cad-protocol`. Expected: PASS, coverage ≥ 80%.

### Task 3: C# Core

**Files:**
- Create in `ExecutionServer.Core`: `Ipc/FrameCodec.cs`, `Ipc/IpcException.cs`, `Ipc/IpcSession.cs` (keep under 400 lines; split out `Ipc/ChunkWriter.cs`, `Ipc/RpcFrames.cs` as needed), `Ipc/SessionConfig.cs`, `Ipc/ICommandHandler.cs`, `Ipc/IFrameSink.cs`, `Ledger/OperationLedger.cs` (delete the `.gitkeep`s in `Ipc/` and `Ledger/`; leave `Units/` alone)
- Create in `ExecutionServer.Tests`: `FrameCodecTests.cs`, `OperationLedgerTests.cs`, `IpcSessionTests.cs`, `TranscriptReplayTests.cs`, `GeneratedTypesTests.cs`, `Support/Fixtures.cs` (finds the repo root by walking up to `schemas/`), `Support/ScriptedHandler.cs`
- Modify: `ExecutionServer.Tests.csproj`: add `coverlet.collector`

**Interfaces (Produces):**

```csharp
public interface IFrameSink { void Write(byte[] payload); void Close(); }   // thread-safe; frames never interleave
public interface ICommandHandler {
    JToken Snapshot(SnapshotParams p, CancellationToken ct);
    JToken Execute(string document, Operation op, CancellationToken ct);    // throws IpcException on failure
}
public sealed class SessionConfig {                                          // immutable
    string Token; HelloResult Hello; bool VersionSupported;
    string UnsupportedMessage; int MaxFrameBytes = 64 * 1024 * 1024;
}
public sealed class IpcSession {
    IpcSession(SessionConfig config, OperationLedger ledger, ICommandHandler handler, IFrameSink sink);
    void Receive(byte[] payload);          // pipe thread
    bool RunNext();                        // UI thread: runs one queued command; false if none
    void Notify(string method, JToken? p); // either thread
    bool IsClosed { get; }
}
public sealed class OperationLedger {      // thread-safe; outlives sessions
    bool TryGet(string operationId, out JToken? result);
    void Record(string document, string operationId, JToken? result);
    IReadOnlyList<string> CompletedIds();  // completion order
    void ForgetDocument(string document);
}
public static class FrameCodec {
    byte[] Encode(byte[] payload, int maxBytes);
    byte[]? Read(Stream stream, int maxBytes); // null at clean end; FrameException on truncated or oversize, before allocating the body
}
public sealed class IpcException : Exception { string Code; JToken? Details; }
```

Behaviour: §8.7. `IpcSession` uses one lock for its state and never holds it while calling the handler. Token comparison is constant-time. `Receive` on a closed session does nothing. After close, `RunNext` still finishes a command already taken, and a write to a closed sink is swallowed; queued commands are dropped.

**Transcript replay harness:** for each scenario whose `sides` has `csharp`, build a session from `config`; feed `core_to_addin` frames to `Receive`; run `RunNext` until empty at the point where an `addin_to_core` frame is due; emit notifications through `Notify` from the transcript at their position; compare what the sink got with the expected frames using §8.7 masking, joining chunks first. `ScriptedHandler` takes results from the transcript (by request id, or by operation ID for `ops.apply`), and records calls so a test can assert the handler was not called. For `cancel_running`, the handler calls `Receive` for the `job.cancel` frame while running, then honours the token. Compare numbers by value (`1` equals `1.0`).

- [ ] **Step 1: Failing tests:**
  - `FrameCodecTests`: `Golden_bytes`, `Round_trip`, `Truncated_header_and_body_throw`, `Oversize_rejected_before_body`, `Clean_end_returns_null`
  - `OperationLedgerTests`: `Records_in_completion_order`, `TryGet_returns_original_result`, `ForgetDocument_removes_only_its_entries`, `Thread_safe_under_parallel_record`
  - `IpcSessionTests`: `Token_never_appears_in_exception_or_ToString`, `Constant_time_compare_handles_length_mismatch`, `Requests_after_close_ignored`, `Parse_failure_answers_minus_32700_with_null_id`, `Non_request_shape_answers_minus_32600`, `Ping_answered_without_RunNext`, `Completed_operations_answered_without_RunNext`, `Commands_run_one_at_a_time_in_order`, `Parallel_receive_and_runnext_answer_each_once` (a background thread, no sleeps), `Cancel_when_idle_answers_false`, `Cancel_stops_batch_with_exec_cancelled_outcome`, `Handler_exception_answers_minus_32603_without_stack_trace`, `Completed_ops_survive_unexpected_exception`, `Duplicate_does_not_call_handler`, `Command_running_at_close_records_in_ledger`, `New_session_sees_ledger`, `Chunked_response_frames_stay_within_limit`, `Small_response_is_one_frame`, `Notify_after_close_ignored`
  - `TranscriptReplayTests`: `[Theory]` over every `csharp` scenario; a `[Fact]` that the list is non-empty and includes `handshake`, `cancel_running`, `snapshot_chunked`, `ops_duplicate`
  - `GeneratedTypesTests`: `[Theory]` over `valid/*`: every instance deserializes; `[Theory]` over `invalid/structural_*`: every instance throws; `Unknown_fields_ignored`; `Error_codes_match_catalogue`
- [ ] **Step 2:** Run the C# suite. Expected: FAIL (compile errors count, since the types don't exist yet; note that in the report).
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the C# suite and `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj --collect:"XPlat Code Coverage"`; report `Core` line coverage excluding `*.g.cs`. Expected: PASS, coverage ≥ 80% (15.6). Run the Python suite. Expected: PASS.

## Out of scope (next milestones)

- The real pipe: `NamedPipe` transport, session-file discovery (8.6.1), heartbeat thread, the add-in's pipe host and UI-thread dispatch (`ExecutionServer.AddIn`, which needs SOLIDWORKS to build), `ui_blocked` timing.
- The adapters that produce snapshots; generated C# types for the snapshot.
- `features.read`, `geometry.candidates` and other operation groups (6.5.2, later increments).
- `ExecutionServer.Core/Units/`.
- Enforcing coverage in CI.
